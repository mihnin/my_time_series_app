import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
from pandas import ExcelWriter
import io
import os
import uuid
import logging
import asyncio
from typing import Optional, List, Union
from minio import Minio
from minio.error import S3Error
from training.model import TrainingParameters
from train_prediciton_save.router import run_training_prediction_async
from sessions.utils import (
    create_session_directory,
    get_model_path,
    training_sessions,
    get_session_path
)
from prediction.router import predict_timeseries
from AutoML.manager import automl_manager

router = APIRouter()

class TrainPredictRequest(BaseModel):
    minio_file_id: str
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
    
def get_minio_client():
    # TODO: заменить на реальные значения или вынести в конфиг
    minio_endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
    minio_access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    minio_secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    minio_secure = os.getenv('MINIO_SECURE', '0') == '1'
    return Minio(
        minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=minio_secure
    )

def get_file_from_minio(file_id: str) -> bytes:
    # file_id формат: <bucket>/<object>
    if '/' not in file_id:
        raise HTTPException(status_code=400, detail='minio_file_id должен быть в формате <bucket>/<object>')
    bucket, object_name = file_id.split('/', 1)
    client = get_minio_client()
    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f'Ошибка получения файла из MinIO: {str(e)}')


class FileResponse(BaseModel):
    fileId: str
    fileName: str
    mimeType: str


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

def create_basic_prediction_file(session_id: str) -> bytes:
    """
    Создаёт базовый Excel файл с прогнозом без метаинформации.
    Используется как fallback, если создание расширенного файла не удалось.
    """
    session_path = get_session_path(session_id)
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    
    if not os.path.exists(prediction_file_path):
        raise FileNotFoundError(f"Файл прогноза не найден: {prediction_file_path}")
    
    with open(prediction_file_path, "rb") as f:
        return f.read()

def create_enhanced_prediction_file(session_id: str) -> bytes:
    """
    Создаёт Excel файл с прогнозом и дополнительными листами с метаинформацией:
    - Prediction: основной прогноз
    - Leaderboard: результаты моделей
    - TrainingParams: параметры обучения
    - WeightedEnsemble: веса ансамбля
    - Messages: сообщения из metadata
    - PyCaret_Leaderboards: детальные результаты PyCaret
    """
    session_path = get_session_path(session_id)
    
    # Основной файл прогноза
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    if not os.path.exists(prediction_file_path):
        raise FileNotFoundError(f"Файл прогноза не найден: {prediction_file_path}")
    
    # Читаем основной прогноз
    try:
        df_pred = pd.read_excel(prediction_file_path)
    except Exception as e:
        raise Exception(f"Ошибка чтения файла прогноза: {e}")

    # Пути к дополнительным файлам
    leaderboard_path = os.path.join(session_path, "leaderboard.csv")
    metadata_path = os.path.join(session_path, "metadata.json")

    # Читаем leaderboard
    df_leaderboard = None
    if os.path.exists(leaderboard_path):
        try:
            df_leaderboard = pd.read_csv(leaderboard_path)
        except Exception as e:
            logging.warning(f"Не удалось прочитать leaderboard: {e}")

    # Читаем параметры обучения
    params_dict = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            params_dict = metadata.get("training_parameters", {})
        except Exception as e:
            logging.warning(f"Не удалось прочитать параметры обучения: {e}")

    # Читаем веса WeightedEnsemble
    weights_dict = None
    if 'autogluon' in [strategy.name for strategy in automl_manager.get_strategies()]:
        autogluon_metadata = os.path.join(session_path, "autogluon", "model_metadata.json")
        if os.path.exists(autogluon_metadata):
            try:
                with open(autogluon_metadata, "r", encoding="utf-8") as f:
                    model_metadata = json.load(f)
                weights_dict = model_metadata.get("weightedEnsemble", None)
            except Exception as e:
                logging.warning(f"Не удалось прочитать веса WeightedEnsemble: {e}")

    # Читаем leaderboard PyCaret по каждому уникальному id
    pycaret_leaderboards = []
    pycaret_leaderboards_dir = os.path.join(session_path, 'pycaret', 'id_leaderboards')
    if os.path.exists(pycaret_leaderboards_dir):
        for fname in os.listdir(pycaret_leaderboards_dir):
            if fname.startswith('leaderboard_') and fname.endswith('.csv'):
                unique_id = fname[len('leaderboard_'):-4]
                try:
                    df_lb = pd.read_csv(os.path.join(pycaret_leaderboards_dir, fname))
                    df_lb.insert(0, 'unique_id', unique_id)
                    # Добавляем разделитель
                    pycaret_leaderboards.append(pd.DataFrame({'unique_id': [f'--- {unique_id} ---'], **{col: [''] for col in df_lb.columns if col != 'unique_id'}}))
                    pycaret_leaderboards.append(df_lb)
                except Exception as e:
                    logging.warning(f"Не удалось прочитать leaderboard для PyCaret id={unique_id}: {e}")

    # Создаём многолистовой Excel файл
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Лист 1 - Основной прогноз
        df_pred.to_excel(writer, sheet_name="Prediction", index=False)
        
        # Лист 2 - Leaderboard
        if df_leaderboard is not None:
            df_leaderboard.to_excel(writer, sheet_name="Leaderboard", index=False)
            # Подсветка лучшей модели зелёным
            workbook = writer.book
            worksheet = writer.sheets["Leaderboard"]
            green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
            if not df_leaderboard.empty:
                worksheet.set_row(1, None, green_format)
        else:
            pd.DataFrame({"info": ["Leaderboard not found"]}).to_excel(writer, sheet_name="Leaderboard", index=False)
        
        # Лист 3 - Параметры обучения
        if params_dict is not None:
            pd.DataFrame(list(params_dict.items()), columns=["Parameter", "Value"]).to_excel(writer, sheet_name="TrainingParams", index=False)
        else:
            pd.DataFrame({"info": ["Training parameters not found"]}).to_excel(writer, sheet_name="TrainingParams", index=False)
        
        # Лист 4 - Веса WeightedEnsemble
        if weights_dict is not None and isinstance(weights_dict, dict) and len(weights_dict) > 0:
            pd.DataFrame(list(weights_dict.items()), columns=["Model", "Weight"]).to_excel(writer, sheet_name="WeightedEnsemble", index=False)
        else:
            pd.DataFrame({"info": ["WeightedEnsemble weights not found"]}).to_excel(writer, sheet_name="WeightedEnsemble", index=False)
        
        # Лист 5 - Сообщения из metadata
        messages = None
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                messages = metadata.get("messages", None)
            except Exception as e:
                logging.warning(f"Не удалось прочитать messages из metadata.json: {e}")
        
        if messages and isinstance(messages, list) and len(messages) > 0:
            pd.DataFrame({"messages": messages}).to_excel(writer, sheet_name="Messages", index=False)
        else:
            pd.DataFrame({"info": ["Messages not found"]}).to_excel(writer, sheet_name="Messages", index=False)
        
        # Лист 6 - PyCaret Leaderboards
        if pycaret_leaderboards:
            df_pycaret_all = pd.concat(pycaret_leaderboards, ignore_index=True)
            df_pycaret_all.to_excel(writer, sheet_name="PyCaret_Leaderboards", index=False)
        else:
            pd.DataFrame({"info": ["PyCaret leaderboards not found"]}).to_excel(writer, sheet_name="PyCaret_Leaderboards", index=False)
    
    output.seek(0)
    return output.getvalue()

def upload_file_to_minio(file_bytes: bytes, bucket: str, object_name: str, content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
    client = get_minio_client()
    found = client.bucket_exists(bucket)
    if not found:
        client.make_bucket(bucket)
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type
    )

@router.post("/train_predict_base64/", response_model=TrainPredictResponse)
async def train_predict_base64(request: TrainPredictRequest):
    """
    Эндпоинт для обучения модели и прогноза по Excel файлам, получаемым из MinIO.
    1. Получает id файла в MinIO (minio_file_id: <bucket>/<object>)
    2. Скачивает файл из MinIO
    3. Запускает обучение
    4. Делает прогноз
    5. Загружает прогноз в MinIO в ту же папку
    6. Возвращает fileId, fileName, mimeType
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
        # Получаем файл из MinIO
        try:
            train_file_bytes = get_file_from_minio(request.minio_file_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка получения файла из MinIO: {str(e)}")
        # Загружаем данные для обучения
        try:
            df_train = pd.read_excel(io.BytesIO(train_file_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel файла: {str(e)}")
        logging.info(f"[train_predict_base64] Файл из MinIO загружен. Train shape: {df_train.shape}")
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
        # --- Новый блок: загрузка прогноза в MinIO ---
        # Определяем bucket и папку исходного файла
        src_file_id = request.minio_file_id
        if '/' not in src_file_id:
            raise HTTPException(status_code=400, detail='minio_file_id должен быть в формате <bucket>/<object>')
        bucket, src_object = src_file_id.split('/', 1)
        src_dir = os.path.dirname(src_object)
        pred_filename = f"prediction_with_metadata_{session_id}.xlsx"
        if src_dir and src_dir != ".":
            pred_object = f"{src_dir}/{pred_filename}"
        else:
            pred_object = pred_filename
        # Генерируем файл прогноза
        try:
            enhanced_file_bytes = create_enhanced_prediction_file(session_id)
        except Exception as e:
            logging.error(f"[train_predict_base64] Ошибка создания файла прогноза: {e}")
            raise HTTPException(status_code=500, detail="Ошибка создания файла прогноза")
        # Загружаем прогноз в MinIO
        try:
            upload_file_to_minio(
                enhanced_file_bytes,
                bucket=bucket,
                object_name=pred_object,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            logging.error(f"[train_predict_base64] Ошибка загрузки прогноза в MinIO: {e}")
            raise HTTPException(status_code=500, detail="Ошибка загрузки прогноза в MinIO")
        # Возвращаем fileId, fileName, mimeType
        file_id = f"{bucket}/{pred_object}"
        return TrainPredictResponse(
            files=[FileResponse(
                fileId=file_id,
                fileName=pred_filename,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )],
            session_id=session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[train_predict_base64] Ошибка для session_id={session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")
