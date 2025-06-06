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

import pandas as modin_pd
from db.db_manager import upload_df_to_db
from db.jwt_logic import get_current_user_db_creds
from db.db_manager import auto_convert_dates
from prediction.router import predict_timeseries, save_prediction
from training.model import TrainingParameters
from training.router import train_model, get_training_status, prepare_training_data_and_status, optional_oauth2_scheme
from src.validation.data_validation import validate_dataset
from sessions.utils import (
    create_session_directory,
    save_session_metadata,
    cleanup_old_sessions,
    get_model_path,
    training_sessions
)

# Global training status tracking

# Run cleanup of old sessions at startup
cleanup_old_sessions()

router = APIRouter()

async def run_training_prediction_async(
    session_id: str,
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    original_filename: str,
    token: str
):
    """Асинхронный запуск процесса обучения."""
    try:
        logging.info(f"[run_training_async] Запуск обучения для session_id={session_id}, файл: {original_filename}")
        session_path = create_session_directory(session_id)
        status = training_sessions[session_id]
        logging.info(f"[run_training_async] Статус сессии до обновления: {status}")
        status.update({
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": 0,
            "session_path": session_path,
            "original_filename": original_filename,
            "training_parameters": training_params.model_dump()
        })
        logging.info(f"[run_training_async] Статус сессии после обновления: {status}")
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
        logging.info(f"[run_training_async] Статус после валидации: {status}")
        save_session_metadata(session_id, status)
        
        # 2. Setup model directory
        model_path = get_model_path(session_id)
        os.makedirs(model_path, exist_ok=True)
        logging.info(f"[run_training_async] Каталог модели создан: {model_path}")

        text_to_progress = {
            'preparation': 10,
            'holidays': 20,
            'missings': 30,
            'dataframe': 40,
            'training': 50,
            'metadata': 60
        }

        # Run the actual training process in a thread pool
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
            "status": "Начинаем прогноз",
            "end_time": datetime.now().isoformat(),
            "progress": 70,
            "model_path": model_path,
            "training_parameters": training_params.model_dump()  # сохраняем параметры обучения в финальном статусе
        })

        save_session_metadata(session_id, status)
        training_sessions[session_id] = status
        logging.info(f"[run_training_async] Обучение завершено успешно для session_id={session_id}")

        logging.info(f"[predict_timeseries] Начало прогноза для session_id={session_id}")

        preds = await asyncio.to_thread(predict_timeseries, session_id)


        output = BytesIO()
        preds.to_excel(output, index=False)
        output.seek(0)
        save_prediction(output, session_id)

        for col in [str(round(x/10, 1)) for x in range(1, 10)]:
            if col in preds.columns:
                preds.drop(columns=[col], inplace=True)


        
        # Исправлено: используем upload_table_name и upload_table_schema для сохранения прогноза в БД
        if getattr(training_params, 'upload_table_name', None):
            table_name = getattr(training_params, 'upload_table_name')
            schema = getattr(training_params, 'upload_table_schema', None)
            db_creds = None
            if token is not None:
                db_creds = await get_current_user_db_creds(token)
            else:
                raise ValueError("Не передан токен или request для получения учетных данных БД")
            username = db_creds["username"]
            password = db_creds["password"]

            logging.info(f"[run_training_async] Начинается загрузка прогноза в таблицу '{table_name}' базы данных (схема: {schema})...")
            if schema:
                preds = auto_convert_dates(preds)
                await upload_df_to_db(preds, schema, table_name, username, password)
            else:
                preds = auto_convert_dates(preds)
                await upload_df_to_db(preds, table_name, username, password)
            logging.info(f"[run_training_async] Прогноз успешно загружен в таблицу '{table_name}' базы данных (схема: {schema}).")

        # Гарантированно обновляем статус после загрузки в БД
        status.update({"progress": 100, 'status': 'completed'})
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status

    except Exception as e:
        error_msg = str(e)
        logging.error(f"[run_training_async] Ошибка обучения в сессии {session_id}: {error_msg}", exc_info=True)
        status = training_sessions[session_id]
        status.update({
            "status": "failed",
            "error": error_msg,
            "end_time": datetime.now().isoformat()
        })
        logging.info(f"[run_training_async] Статус после ошибки: {status}")
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status


def save_df_to_parquet(df, path):
    df.to_parquet(path)




@router.post("/train_prediction_save/")
async def train_model_endpoint(
    request: Request,
    params: str = Form(...),
    training_file: UploadFile = File(None),
    background_tasks: BackgroundTasks = None,
    token: Optional[str] = Depends(optional_oauth2_scheme),
):
    """Запуск асинхронного процесса обучения и возврат session_id для отслеживания статуса.
    Если в параметрах есть download_table_name, то датасет берется из БД, иначе из файла.
    Аутентификация требуется только для загрузки из БД.
    """
    session_id = str(uuid.uuid4())
    try:
        logging.info(f"[train_model_endpoint] Получен запрос на обучение. Файл: {getattr(training_file, 'filename', None)}, Session ID: {session_id}")
        # DEBUG: log filename for troubleshooting
        if training_file:
            logging.info(f"[train_model_endpoint] training_file.filename: {training_file.filename}")
        params_dict = json.loads(params)
        training_params = TrainingParameters(**params_dict)
        logging.info(f"[train_model_endpoint] Параметры обучения для session_id={session_id}: {params_dict}")

        # Используем общую функцию подготовки данных и статуса
        df_train, original_filename, parquet_file_path, session_path, initial_status = await prepare_training_data_and_status(
            session_id=session_id,
            training_params=training_params,
            training_file=training_file,
            request=request,
            token=token
        )
        logging.info(f"[train_model_endpoint] Статус сессии и метаданные сохранены для session_id={session_id}")

        # Start async training
        background_tasks.add_task(
            run_training_prediction_async,
            session_id,
            df_train,
            training_params,
            original_filename,
            token
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