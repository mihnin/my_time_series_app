import base64
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import io
import os
import uuid
import logging
import asyncio
from typing import Optional, List, Union

from training.model import TrainingParameters
from train_prediciton_save.router import run_training_prediction_async
from sessions.utils import (
    create_session_directory,
    get_model_path,
    training_sessions
)
from prediction.router import predict_timeseries

router = APIRouter()

class TrainPredictRequest(BaseModel):
    train_file_base64: str
    datetime_column: str = 'Date'
    target_column: str = 'Target'
    item_id_column: str = 'Shop'
    frequency: Optional[str] = "D"
    fill_missing_method: Optional[str] = "mean"
    fill_group_columns: Optional[List[str]] = []
    use_russian_holidays: Optional[bool] = False
    evaluation_metric: Optional[str] = "MASE"
    models_to_train: Optional[str] = "*"
    autogluon_preset: Optional[str] = "high_quality"
    predict_mean_only: Optional[bool] = True
    prediction_length: Optional[int] = 3
    training_time_limit: Optional[int] = 60
    static_feature_columns: Optional[Union[List[str], str]] = []
    pycaret_models: Optional[str] = None

class FileResponse(BaseModel):
    name: str
    content: str

class TrainPredictResponse(BaseModel):
    files: List[FileResponse]
    session_id: str

def get_default_training_params(request: TrainPredictRequest) -> TrainingParameters:
    """Возвращает параметры обучения на основе запроса"""
    return TrainingParameters(
        datetime_column=request.datetime_column,
        target_column=request.target_column,
        item_id_column=request.item_id_column,
        frequency=request.frequency,
        fill_missing_method=request.fill_missing_method,
        fill_group_columns=request.fill_group_columns,
        use_russian_holidays=request.use_russian_holidays,
        evaluation_metric=request.evaluation_metric,
        models_to_train=request.models_to_train,
        autogluon_preset=request.autogluon_preset,
        predict_mean_only=request.predict_mean_only,
        prediction_length=request.prediction_length,
        training_time_limit=request.training_time_limit,
        static_feature_columns=request.static_feature_columns,
        pycaret_models=request.pycaret_models,
        # Не устанавливаем upload_table_name и upload_table_schema чтобы не загружать в БД
        upload_table_name=None,
        upload_table_schema=None
    )

@router.post("/train_predict_base64/", response_model=TrainPredictResponse)
async def train_predict_base64(request: TrainPredictRequest):
    """
    Эндпоинт для обучения модели и прогноза по Excel файлам в формате base64.
    
    1. Получает файлы в base64
    2. Запускает обучение
    3. Делает прогноз
    4. Возвращает файл с прогнозом в base64
    """
    session_id = str(uuid.uuid4())
    
    try:
        logging.info(f"[train_predict_base64] Начало обработки для session_id={session_id}")
        
        # Обрабатываем static_feature_columns если это строка JSON
        if isinstance(request.static_feature_columns, str) and request.static_feature_columns.strip():
            try:
                request.static_feature_columns = json.loads(request.static_feature_columns)
                logging.info(f"[train_predict_base64] static_feature_columns обработан из строки: {request.static_feature_columns}")
            except json.JSONDecodeError as e:
                logging.warning(f"[train_predict_base64] Не удалось парсить static_feature_columns как JSON: {e}")
                request.static_feature_columns = []
        
        # Создаем параметры обучения из запроса
        training_params = get_default_training_params(request)

        # Декодируем base64 файл
        try:
            train_file_bytes = base64.b64decode(request.train_file_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка декодирования base64: {str(e)}")
        
        # Загружаем данные для обучения
        try:
            df_train = pd.read_excel(io.BytesIO(train_file_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")
        
        logging.info(f"[train_predict_base64] Файл загружен. Train shape: {df_train.shape}")
        
        # Создаем сессию
        session_path = create_session_directory(session_id)
        
        # Инициализируем статус сессии
        training_sessions[session_id] = {
            "status": "initializing",
            "session_id": session_id,
            "session_path": session_path
        }
        
        # Запускаем обучение синхронно (внутри уже происходит и прогноз)
        await run_training_prediction_async(
            session_id=session_id,
            df_train=df_train,
            training_params=training_params,
            original_filename="train_file.xlsx",
            token=""  # Пустой токен для того, чтобы не загружать в БД
        )
        
        # Проверяем статус выполнения
        session_status = training_sessions.get(session_id, {})
        if session_status.get("status") != "completed":
            error_msg = session_status.get("error", "Неизвестная ошибка обучения")
            raise HTTPException(status_code=500, detail=f"Ошибка обучения: {error_msg}")
        
        logging.info(f"[train_predict_base64] Обучение и прогноз завершены для session_id={session_id}")
        
        # Получаем файл с прогнозом, который уже создан функцией run_training_prediction_async
        prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
        if not os.path.exists(prediction_file_path):
            raise HTTPException(status_code=500, detail="Файл с прогнозом не найден")
        
        # Читаем файл с прогнозом в base64
        with open(prediction_file_path, "rb") as f:
            prediction_base64 = base64.b64encode(f.read()).decode('utf-8')
        
        logging.info(f"[train_predict_base64] Успешно завершено для session_id={session_id}")
        
        return TrainPredictResponse(
            files=[FileResponse(
                name=f"prediction_{session_id}.xlsx",
                content=prediction_base64
            )],
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[train_predict_base64] Ошибка для session_id={session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")
