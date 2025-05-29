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


def fill_to_frequency(df: pd.DataFrame, training_params: TrainingParameters, session_id: str = None) -> pd.DataFrame:
    """
    Универсально дополняет каждый временной ряд до нужной частоты (freq) и заполняет пропуски.
    Если передан session_id, пишет сообщения о дополнении в metadata.json только для реально дополненных рядов.
    Также пишет предупреждение, если после дополнения данных недостаточно для полноценного прогноза.
    Если данных недостаточно, такие ряды сохраняются в отдельный файл с наивным прогнозом и исключаются из датасета для обучения.
    """
    freq = training_params.frequency
    if not freq or freq.lower() == 'auto':
        return df
    freq_short = freq.split()[0]
    id_col = training_params.item_id_column
    dt_col = training_params.datetime_column
    tgt_col = training_params.target_column
    prediction_length = getattr(training_params, 'prediction_length', 1)
    min_required = max(prediction_length + 1, 5) + prediction_length
    messages = []
    method = 'ffill'  # сейчас всегда ffill, но можно расширить
    naive_forecasts = []
    # Если нет группировки по id, просто по всему датафрейму
    if id_col not in df.columns:
        df = df.copy()
        df[dt_col] = pd.to_datetime(df[dt_col])
        full_range = pd.date_range(df[dt_col].min(), df[dt_col].max(), freq=freq_short)
        if len(full_range) > len(df):
            df = df.set_index(dt_col).reindex(full_range).rename_axis(dt_col).reset_index()
            df[tgt_col] = df[tgt_col].ffill()
            messages.append(f"Ряд дополнен до частоты {freq_short} методом {method}")
        else:
            df = df.set_index(dt_col).reindex(full_range).rename_axis(dt_col).reset_index()
            df[tgt_col] = df[tgt_col].ffill()
        # Проверка на минимальное количество данных
        if len(df) < min_required:
            messages.append("Для ряда невозможно выполнить полноценный прогноз из-за малого количества данных. Выполнен наивный прогноз.")
            # Формируем наивный прогноз: берём последнее значение и генерируем prediction_length дат вперёд
            if len(df) > 0:
                last_date = df[dt_col].max()
                last_value = df[tgt_col].iloc[-1]
                future_dates = pd.date_range(last_date, periods=prediction_length+1, freq=freq_short)[1:]
                naive_df = pd.DataFrame({
                    dt_col: future_dates,
                    tgt_col: [last_value]*prediction_length
                })
                naive_forecasts.append(naive_df)
            df = df.iloc[0:0]  # полностью исключаем из обучения
    else:
        dfs = []
        for unique_id, group in df.groupby(id_col):
            group = group.copy()
            group[dt_col] = pd.to_datetime(group[dt_col])
            full_range = pd.date_range(group[dt_col].min(), group[dt_col].max(), freq=freq_short)
            was_extended = len(full_range) > len(group)
            group = group.set_index(dt_col).reindex(full_range).rename_axis(dt_col).reset_index()
            group[id_col] = unique_id
            group[tgt_col] = group[tgt_col].ffill()
            # Проверка на минимальное количество данных для каждого ряда
            if len(group) < min_required:
                messages.append(f"Для ряда с id {unique_id} невозможно выполнить полноценный прогноз из-за малого количества данных. Выполнен наивный прогноз.")
                if len(group) > 0:
                    last_date = group[dt_col].max()
                    last_value = group[tgt_col].iloc[-1]
                    future_dates = pd.date_range(last_date, periods=prediction_length+1, freq=freq_short)[1:]
                    naive_df = pd.DataFrame({
                        dt_col: future_dates,
                        tgt_col: [last_value]*prediction_length,
                        id_col: [unique_id]*prediction_length
                    })
                    naive_forecasts.append(naive_df)
                continue  # не добавляем в dfs, исключаем из обучения
            dfs.append(group)
            if was_extended:
                messages.append(f"Ряд с id {unique_id} дополнен до частоты {freq_short} методом {method}")
        df = pd.concat(dfs, ignore_index=True) if dfs else df.iloc[0:0]
    # Сохраняем наивные ряды в отдельный файл, если есть такие
    naive_forecast_path = None
    if naive_forecasts and session_id is not None:
        session_path = get_session_path(session_id)
        naive_forecast_path = os.path.join(session_path, f"naive_forecast_{session_id}.csv")
        pd.concat(naive_forecasts, ignore_index=True).to_csv(naive_forecast_path, index=False)
    # Сохраняем очищенный датасет (без рядов с малым количеством данных) в parquet для обучения и прогноза
    if session_id is not None:
        session_path = get_session_path(session_id)
        parquet_file_path = os.path.join(session_path, "training_data.parquet")
        df.to_parquet(parquet_file_path, index=False)
    # Сохраняем messages и путь к наивному прогнозу в metadata.json если есть session_id
    if session_id is not None and session_id in training_sessions:
        status = training_sessions[session_id]
        if messages:
            if 'messages' not in status:
                status['messages'] = []
            status['messages'].extend(messages)
        if naive_forecast_path:
            status['naive_forecast_path'] = naive_forecast_path
        save_session_metadata(session_id, status)
    return df

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
        
        # --- Сохраняем статические данные в static_data.parquet ---
        id_col = training_params.item_id_column
        static_cols = training_params.static_feature_columns
        if static_cols and id_col in df2.columns:
            # static_cols: список названий статических признаков
            static_cols = [col for col in static_cols if col in df2.columns and col != id_col]
            if static_cols:
                static_df = df2[[id_col] + static_cols].drop_duplicates(subset=[id_col])
                session_path = get_session_path(session_id)
                static_path = os.path.join(session_path, 'static_data.parquet')
                print(static_df)
                static_df.to_parquet(static_path, index=False)
                logging.info(f"[train_model] Статические данные сохранены: {static_path}")

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

        # Fill missing values (custom logic)
        df2 = fill_missing_values(
            df2,
            training_params.fill_missing_method,
            training_params.fill_group_columns
        )
        logging.info(f"[train_model] Пропущенные значения обработаны методом: {training_params.fill_missing_method}")
        status.update({"progress": text_to_progress['missings']})
        save_session_metadata(session_id, status)

        # Универсальное дополнение до нужной частоты + запись messages
        df2 = fill_to_frequency(df2, training_params, session_id=session_id)
        logging.info(f"[train_model] Данные дополнены до частоты {training_params.frequency}")

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
    print(training_file.filename)
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
        # DEBUG: log filename for troubleshooting
        logging.info(f"[prepare_training_data_and_status] Received file: {getattr(training_file, 'filename', None)}")
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