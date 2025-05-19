from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, BackgroundTasks
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

import modin.pandas as modin_pd
from autogluon.timeseries import TimeSeriesPredictor
from prediction.router import predict_timeseries, save_prediction
from training.model import TrainingParameters
from training.router import train_model
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
from training.router import get_training_status

# Global training status tracking

# Run cleanup of old sessions at startup
cleanup_old_sessions()

router = APIRouter()

async def run_training_prediction_async(
    session_id: str,
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    original_filename: str
):
    """Асинхронный запуск процесса обучения."""
    try:
        logging.info(f"[run_training_async] Запуск обучения для session_id={session_id}, файл: {original_filename}")
        # Create session directory and save initial status
        session_path = create_session_directory(session_id)
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
        preds.reset_index().to_excel(output, index=False)
        output.seek(0)

        save_prediction(output, session_id)

        status.update({"progress": 100, 'status': 'completed'})

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


def save_df_to_parquet(df, path):
    df.to_parquet(path)




@router.post("/train_prediction_save/")
async def train_model_endpoint(
    params: str = Form(...),
    training_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """Запуск асинхронного процесса обучения и возврат session_id для отслеживания статуса."""
    session_id = str(uuid.uuid4()) # Генерируем ID сессии в начале для логирования ошибок
    try:
        logging.info(f"[train_model_endpoint] Получен запрос на обучение. Файл: {training_file.filename}, Session ID: {session_id}")
        
        # Parse parameters
        params_dict = json.loads(params)
        training_params = TrainingParameters(**params_dict)
        logging.info(f"[train_model_endpoint] Параметры обучения для session_id={session_id}: {params_dict}")

        # Validate file type
        if not training_file.filename.endswith((".csv", ".xlsx", ".xls")):
            logging.error(f"Неверный тип файла для session_id={session_id}: {training_file.filename}")
            raise HTTPException(
                status_code=400, 
                detail="Неверный тип файла. Пожалуйста, загрузите CSV или Excel файл."
            )

        # Create session directory
        session_path = create_session_directory(session_id)
        logging.info(f"[train_model_endpoint] Создана новая сессия и каталог: {session_id} по пути {session_path}")

        # 1. Чтение файла в память
        file_content = await training_file.read() # Читаем содержимое файла один раз

        # 2. Сохранение ОРИГИНАЛЬНОГО файла (опционально, но может быть полезно для аудита)
        original_file_path = os.path.join(session_path, f"original_{training_file.filename}")
        with open(original_file_path, "wb") as f:
            f.write(file_content)
        logging.info(f"[train_model_endpoint] Оригинальный файл сохранён: {original_file_path} для session_id={session_id}")
        
        # 3. Загрузка DataFrame из содержимого файла (file_content)
        # Оборачиваем байты в BytesIO, чтобы pandas мог их прочитать как файл
        file_like_object = BytesIO(file_content)
        
        # Используем to_thread для блокирующих операций pandas
        def read_data_from_stream(stream, filename):
            if filename.endswith('.csv'):
                return modin_pd.read_csv(stream)._to_pandas()
            else:  # Excel file
                return modin_pd.read_excel(stream)._to_pandas() # engine='openpyxl' if filename.endswith('.xlsx') else None

        try:
            logging.info(f"[train_model_endpoint] Начало загрузки данных в DataFrame для session_id={session_id}...")
            df_train = await asyncio.to_thread(read_data_from_stream, file_like_object, training_file.filename)
            logging.info(f"[train_model_endpoint] Данные успешно загружены в DataFrame из файла: {training_file.filename} для session_id={session_id}. Форма DataFrame: {df_train.shape}")
        except Exception as e:
            logging.error(f"Ошибка чтения файла в DataFrame для session_id={session_id}: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Ошибка чтения данных из файла: {str(e)}")
        finally:
            file_like_object.close() # Закрываем BytesIO

        # 4. Сохранение DataFrame в формате Parquet для быстрого доступа в будущем
        # Это будет файл, который может использоваться для прогнозов или повторного обучения
        parquet_file_name = "training_data.parquet" # Стандартное имя
        parquet_file_path = os.path.join(session_path, parquet_file_name)
        
      
        await asyncio.to_thread(save_df_to_parquet, df_train, parquet_file_path)
        logging.info(f"[train_model_endpoint] DataFrame сохранён в формате Parquet: {parquet_file_path} для session_id={session_id}")

        # Initialize session status
        initial_status = {
            "status": "initializing",
            "create_time": datetime.now().isoformat(),
            "original_file_name": training_file.filename, # Имя оригинального файла
            "processed_file_path": parquet_file_path, # Путь к Parquet файлу для дальнейшего использования
            "session_path": session_path,
            "progress": 0
        }
        training_sessions[session_id] = initial_status
        save_session_metadata(session_id, initial_status) # Сохраняем метаданные сессии
        logging.info(f"[train_model_endpoint] Статус сессии и метаданные сохранены для session_id={session_id}")

        # Start async training
        background_tasks.add_task(
            run_training_prediction_async,
            session_id,
            df_train, # Передаем уже загруженный DataFrame
            training_params,
            training_file.filename # Передаем имя оригинального файла для информации в статусе
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
    except ValueError as e: # Может быть выброшено TrainingParameters
        logging.error(f"Ошибка валидации параметров для session_id={session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=422, # Unprocessable Entity
            detail=f"Ошибка валидации параметров: {str(e)}"
        )
    except HTTPException: # Перехватываем HTTPException, чтобы не попасть в общий Exception
        raise
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при запуске обучения для session_id={session_id}: {e}", exc_info=True)
        # Обновляем статус сессии на 'failed', если он уже был инициализирован
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
        if training_file: # Убедимся, что training_file существует
            await training_file.close()