from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, BackgroundTasks, Request
import pandas as pd
import numpy as np
import logging
import gc
import os
import json
import uuid
import asyncio
from functools import partial
from typing import Dict, Optional
from datetime import datetime
from io import BytesIO
from AutoML.manager import automl_manager
from db.db_manager import fetch_table_as_dataframe
from db.jwt_logic import get_current_user_db_creds, oauth2_scheme
from db.settings import settings as db_settings
from fastapi.security import OAuth2PasswordBearer
from typing import Optional

import pandas as modin_pd
from autogluon.timeseries import TimeSeriesPredictor
from .model import TrainingParameters
from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries, safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from src.validation.data_validation import validate_dataset
from sessions.utils import (
    create_session_directory,
    get_session_path,
    save_session_metadata,
    load_session_metadata,
    cleanup_old_sessions,
    save_training_file,
    get_model_path,
    training_sessions
)

# Global training status tracking


# Run cleanup of old sessions at startup
cleanup_old_sessions()

router = APIRouter()

def get_training_status(session_id: str) -> Optional[Dict]:
    """Get the current status of a training session."""
    if session_id not in training_sessions:
        # Try to load from file
        try:
            metadata = load_session_metadata(session_id)
            if metadata:
                training_sessions[session_id] = metadata
        except:
            return None
    return training_sessions.get(session_id)

async def run_training_async(
    session_id: str,
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    original_filename: str,
):
    """Асинхронный запуск процесса обучения."""
    try:
        logging.info(f"[run_training_async] Запуск обучения для session_id={session_id}, файл: {original_filename}")
        # Create session directory and save initial status
        session_path = get_session_path(session_id)
        status = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": 0,
            "session_path": session_path,
            "original_filename": original_filename,
            "training_parameters": training_params.model_dump() 
        }
        training_sessions[session_id] = status
        save_session_metadata(session_id, status)

        # 1. Initial validation
        logging.info(f"[run_training_async] Валидация данных...")
        validation_results = validate_dataset(
            df_train, 
            training_params.datetime_column,
            training_params.target_column,
            training_params.item_id_column
        )
        if not validation_results["is_valid"]:
            error_message = "Данные не прошли валидацию: " + "; ".join(validation_results["errors"])
            logging.error(f"[run_training_async] Ошибка валидации: {error_message}")
            raise ValueError(error_message)
        logging.info(f"[run_training_async] Валидация успешно пройдена.")

        status.update({"progress": 10})
        save_session_metadata(session_id, status)
        
        # 2. Setup model directory
        model_path = get_model_path(session_id)
        os.makedirs(model_path, exist_ok=True)
        logging.info(f"[run_training_async] Каталог модели создан: {model_path}")

        # Run the actual training process in a thread pool

        text_to_progress = {
            'preparation': 20,
            'holidays': 30,
            'missings': 40,
            'dataframe': 50,
            'training': 60,
            'metadata': 90
        }

        train_func = partial(
            train_model,
            df_train=df_train,
            training_params=training_params,
            model_path=model_path,
            session_id=session_id,
            text_to_progress=text_to_progress
        )
        logging.info(f"[run_training_async] Передача задачи обучения в пул потоков...")
        await asyncio.to_thread(train_func)

        # Update final status
        status.update({
            "status": "completed",
            "end_time": datetime.now().isoformat(),
            "progress": 100,
            "model_path": model_path,
            "training_parameters": training_params.model_dump()  # сохраняем параметры обучения в финальном статусе
        })
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status
        logging.info(f"[run_training_async] Обучение завершено успешно для session_id={session_id}")

    except Exception as e:
        error_msg = str(e)
        logging.error(f"[run_training_async] Ошибка обучения в сессии {session_id}: {error_msg}", exc_info=True)
        status = training_sessions[session_id]
        status.update({
            "status": "failed",
            "error": error_msg,
            "end_time": datetime.now().isoformat()
        })
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status


def train_model(
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    model_path: str,
    session_id: str,
    text_to_progress: dict | None
) -> None:
    """Основная функция обучения (запускается в отдельном потоке)."""
    try:
        status = training_sessions[session_id]
        logging.info(f"[train_model] Начало подготовки данных для session_id={session_id}")
        # 3. Data Preparation
        df2 = df_train.copy()
        df2[training_params.datetime_column] = pd.to_datetime(df2[training_params.datetime_column], errors="coerce")
        status.update({"progress": text_to_progress['preparation']}) 
        save_session_metadata(session_id, status)

        # Add holidays if requested
        if training_params.use_russian_holidays:
            df2 = add_russian_holiday_feature(
                df2, 
                date_col=training_params.datetime_column, 
                holiday_col="russian_holiday"
            )
            logging.info(f"[train_model] Добавлен признак российских праздников.")
        status.update({"progress": text_to_progress['holidays']})
        save_session_metadata(session_id, status)

        # Fill missing values
        df2 = fill_missing_values(
            df2,
            training_params.fill_missing_method,
            training_params.fill_group_columns
        )
        logging.info(f"[train_model] Пропущенные значения обработаны методом: {training_params.fill_missing_method}")
        status.update({"progress": text_to_progress['missings']})
        save_session_metadata(session_id, status)


        for strategy in automl_manager.get_strategies():
            strategy.train(df2, training_params, session_id)


        session_path = get_session_path(session_id)
        combined_leaderboard = automl_manager.combine_leaderboards(session_id, [strategy.name for strategy in automl_manager.get_strategies()])
        combined_leaderboard.to_csv(os.path.join(session_path, 'leaderboard.csv'), index=False)
        gc.collect()
        logging.info(f"[train_model] Очистка памяти завершена.")

    except Exception as e:
        logging.error(f"[train_model] Ошибка в процессе обучения: {e}", exc_info=True)
        raise Exception(f"Error in training process: {str(e)}")


@router.get("/training_status/{session_id}")
async def get_session_status(session_id: str):
    """Получить статус сессии обучения. Если завершено — добавить лидерборд."""
    logging.info(f"[get_training_status] Запрос статуса для session_id={session_id}")
    status = get_training_status(session_id)
    if status is None:
        logging.error(f"Сессия не найдена: {session_id}")
        raise HTTPException(status_code=404, detail="Training session not found")
    if status.get("status") == "completed":
        session_path = get_session_path(session_id)
        leaderboard_path = os.path.join(session_path, "leaderboard.csv")
        leaderboard = None
        if os.path.exists(leaderboard_path):
            leaderboard = pd.read_csv(leaderboard_path).to_dict(orient="records")
            logging.info(f"[get_training_status] Лидерборд добавлен к статусу для session_id={session_id}")
        status["leaderboard"] = leaderboard

        # Добавляем pycaret/id_leaderboards
        pycaret_leaderboards_dir = os.path.join(session_path, 'pycaret', 'id_leaderboards')
        pycaret_leaderboards = {}
        if os.path.exists(pycaret_leaderboards_dir):
            for fname in os.listdir(pycaret_leaderboards_dir):
                if fname.endswith('.csv'):
                    unique_id = fname.replace('leaderboard_', '').replace('.csv', '')
                    fpath = os.path.join(pycaret_leaderboards_dir, fname)
                    try:
                        df = pd.read_csv(fpath)
                        pycaret_leaderboards[unique_id] = df.to_dict(orient="records")
                    except Exception as e:
                        logging.error(f"Ошибка чтения pycaret leaderboard для {unique_id}: {e}")
        status["pycaret"] = pycaret_leaderboards
    return status


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def optional_oauth2_scheme(request: Request) -> Optional[str]:
    """
    Позволяет получать токен, если он есть, иначе возвращает None (для публичных эндпоинтов).
    """
    auth: str = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None

@router.post("/train_timeseries_model/")
async def train_model_endpoint(
    request: Request,
    params: str = Form(...),
    training_file: UploadFile = File(None),
    background_tasks: BackgroundTasks = None,
    token: Optional[str] = Depends(optional_oauth2_scheme),
):
    """
    Запуск асинхронного процесса обучения и возврат session_id для отслеживания статуса.
    Если в параметрах есть download_table_name, то датасет берется из БД, иначе из файла.
    Аутентификация требуется только для загрузки из БД.
    """
    session_id = str(uuid.uuid4())
    try:
        logging.info(f"[train_model_endpoint] Получен запрос на обучение. Session ID: {session_id}")
        params_dict = json.loads(params)
        training_params = TrainingParameters(**params_dict)
        logging.info(f"[train_model_endpoint] Параметры обучения для session_id={session_id}: {params_dict}")

        # Используем общую функцию подготовки данных и статуса
        # --- поддержка работы как с токеном, так и без токена ---
        df_train, original_filename, parquet_file_path, session_path, initial_status = await prepare_training_data_and_status(
            session_id=session_id,
            training_params=training_params,
            training_file=training_file,
            request=request,
            token=token if token else None
        )
        logging.info(f"[train_model_endpoint] Статус сессии и метаданные сохранены для session_id={session_id}")

        background_tasks.add_task(
            run_training_async,
            session_id,
            df_train,
            training_params,
            original_filename
        )
        logging.info(f"[train_model_endpoint] Задача обучения передана в background_tasks для session_id={session_id}")
        return {
            "status": "accepted",
            "message": "Обучение запущено",
            "session_id": session_id
        }
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка разбора JSON параметров для session_id={session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка разбора JSON параметров: {str(e)}"
        )
    except ValueError as e:
        logging.error(f"Ошибка валидации параметров для session_id={session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=422,
            detail=f"Ошибка валидации параметров: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при запуске обучения для session_id={session_id}: {e}", exc_info=True)
        if session_id in training_sessions:
            failed_status = {
                "status": "failed",
                "error": f"Ошибка на этапе инициализации: {str(e)}",
                "end_time": datetime.now().isoformat()
            }
            training_sessions[session_id].update(failed_status)
            save_session_metadata(session_id, training_sessions[session_id])
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера при запуске обучения: {str(e)}"
        )
    finally:
        if training_file:
            await training_file.close()

async def prepare_training_data_and_status(
    session_id: str,
    training_params: TrainingParameters,
    training_file: UploadFile = None,
    request: Request = None,
    token: str = None,
    parquet_file_name: str = "training_data.parquet"
):
    """
    Универсальная функция подготовки данных (из файла или БД) и инициализации статуса сессии.
    Возвращает: df_train, original_filename, parquet_file_path, session_path, initial_status
    """
    import pandas as modin_pd
    from io import BytesIO
    import os
    from db.db_manager import fetch_table_as_dataframe
    from db.jwt_logic import get_current_user_db_creds
    from sessions.utils import create_session_directory, save_session_metadata, training_sessions
    from datetime import datetime
    
    session_path = create_session_directory(session_id)
    parquet_file_path = os.path.join(session_path, parquet_file_name)
    original_file_path = None
    original_filename = None
    
    if hasattr(training_params, 'download_table_name') and getattr(training_params, 'download_table_name', None):
        # Загрузка из БД
        table_name = getattr(training_params, 'download_table_name')
        db_creds = None
        if token is not None:
            db_creds = await get_current_user_db_creds(token)
        elif request is not None:
            db_creds = await get_current_user_db_creds(request)
        else:
            raise ValueError("Не передан токен или request для получения учетных данных БД")
        username = db_creds["username"]
        password = db_creds["password"]
        df_train = await fetch_table_as_dataframe(table_name, username, password)
        if df_train.empty:
            raise HTTPException(status_code=400, detail=f"Таблица {table_name} пуста или не найдена")
        await asyncio.to_thread(df_train.to_parquet, parquet_file_path)
        original_filename = f"from_db_{table_name}.parquet"
    else:
        if not training_file or not training_file.filename.endswith((".csv", ".xlsx", ".xls")):
            raise HTTPException(
                status_code=400,
                detail="Неверный тип файла. Пожалуйста, загрузите CSV или Excel файл."
            )
        file_content = await training_file.read()
        original_file_path = os.path.join(session_path, f"original_{training_file.filename}")
        with open(original_file_path, "wb") as f:
            f.write(file_content)
        file_like_object = BytesIO(file_content)
        def read_data_from_stream(stream, filename):
            if filename.endswith('.csv'):
                return modin_pd.read_csv(stream)
            else:
                return modin_pd.read_excel(stream)
        df_train = await asyncio.to_thread(read_data_from_stream, file_like_object, training_file.filename)
        file_like_object.close()
        await asyncio.to_thread(df_train.to_parquet, parquet_file_path)
        original_filename = training_file.filename
    initial_status = {
        "status": "initializing",
        "create_time": datetime.now().isoformat(),
        "original_file_name": original_filename,
        "processed_file_path": parquet_file_path,
        "session_path": session_path,
        "progress": 0
    }
    training_sessions[session_id] = initial_status
    save_session_metadata(session_id, initial_status)
    return df_train, original_filename, parquet_file_path, session_path, initial_status