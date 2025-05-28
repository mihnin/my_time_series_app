import json
from fastapi import APIRouter, HTTPException, Response
import os
import pandas as pd
from io import BytesIO
from typing import Dict
from autogluon.timeseries import TimeSeriesPredictor
from sessions.utils import (
    get_session_path,
    load_session_metadata,
)
from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe
import logging
from AutoML.manager import automl_manager
import asyncio

from pandas import ExcelWriter

router = APIRouter()

def predict_timeseries(session_id: str):

    logging.info(f"[predict_timeseries] Начало прогноза для session_id={session_id}")
    # 1. Проверяем, что сессия существует
    session_path = get_session_path(session_id)
    if not os.path.exists(session_path):
        logging.error(f"Папка сессии не найдена: {session_path}")
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    # 2. Загружаем metadata
    metadata = load_session_metadata(session_id)
    if not metadata:
        logging.error(f"Файл metadata.json не найден для session_id={session_id}")
        raise HTTPException(status_code=404, detail="metadata.json не найден")
    params = metadata.get("training_parameters")
    if not params:
        logging.error(f"Параметры обучения не найдены в metadata.json для session_id={session_id}")
        raise HTTPException(status_code=400, detail="Параметры обучения не найдены в metadata.json")

    # 3. Загружаем исходный train файл (теперь только parquet)
    parquet_file = os.path.join(session_path, "training_data.parquet")
    if not os.path.exists(parquet_file):
        logging.error(f"Файл с обучающими данными (parquet) не найден для session_id={session_id}")
        raise HTTPException(status_code=404, detail="Файл с обучающими данными (parquet) не найден")
    try:
        df = pd.read_parquet(parquet_file)
        logging.info(f"Файл с обучающими данными успешно загружен: {parquet_file}")
    except Exception as e:
        logging.error(f"Ошибка чтения parquet файла данных: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка чтения parquet файла данных: {e}")

    # 4. Подготовка данных (аналогично обучению)
    dt_col = params["datetime_column"]
    tgt_col = params["target_column"]
    id_col = params["item_id_column"]
    freq = params.get("frequency", "auto")
    fill_method = params.get("fill_missing_method", "None")
    fill_group_cols = params.get("fill_group_columns", [])
    use_holidays = params.get("use_russian_holidays", False)
    static_feats = params.get("static_feature_columns", [])

    df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
    if use_holidays:
        df = add_russian_holiday_feature(df, date_col=dt_col, holiday_col="russian_holiday")
        logging.info("Добавлен признак российских праздников")
    df = fill_missing_values(df, fill_method, fill_group_cols)
    logging.info(f"Пропущенные значения обработаны методом: {fill_method}")

    best_strategy = automl_manager.get_best_strategy(session_id)
    preds = best_strategy.predict(df, session_id, params)

    # Добавляем наивный прогноз, если есть соответствующий файл
    session_path = get_session_path(session_id)
    naive_path = os.path.join(session_path, f"naive_forecast_{session_id}.csv")
    if os.path.exists(naive_path):
        try:
            df_naive = pd.read_csv(naive_path)
            preds = pd.concat([preds, df_naive], ignore_index=True)
        except Exception as e:
            logging.warning(f"Не удалось добавить наивный прогноз: {e}")
    return preds

def save_prediction(output, session_id):

    session_path = get_session_path(session_id)
    
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    with open(prediction_file_path, "wb") as f:

        f.write(output.getvalue())
    logging.info(f"[predict_timeseries] Прогноз сохранён в файл: {prediction_file_path}")

@router.get("/predict/{session_id}")
async def predict_timeseries_endpoint(session_id: str):
    """Сделать прогноз по id сессии и вернуть xlsx файл с результатом."""
    
    preds = await asyncio.to_thread(predict_timeseries, session_id)

    output = BytesIO()
    # Удаляем индекс, если он есть, чтобы не было столбца с цифрами
    
    preds.to_excel(output, index=False)
    output.seek(0)

    save_prediction(output, session_id)
    
    # Возвращаем файл
    logging.info(f"[predict_timeseries] Отправка файла пользователю (session_id={session_id})")
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=prediction_{session_id}.xlsx"
        }
    )

@router.get("/download_prediction/{session_id}")
def download_prediction_file(session_id: str):
    """Скачать ранее сохранённый файл прогноза по id сессии с добавлением leaderboard, параметров и весов."""



    logging.info(f"[download_prediction_file] Запрос на скачивание xlsx для session_id={session_id}")
    session_path = get_session_path(session_id)
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    leaderboard_path = os.path.join(session_path, "leaderboard.csv")
    metadata_path = os.path.join(session_path, "metadata.json")


    # Проверяем наличие файла прогноза
    if not os.path.exists(prediction_file_path):
        logging.error(f"Файл прогноза не найден: {prediction_file_path}")
        raise HTTPException(status_code=404, detail="Файл прогноза не найден")

    # Читаем прогноз
    try:
        df_pred = pd.read_excel(prediction_file_path)
    except Exception as e:
        logging.error(f"Ошибка чтения файла прогноза: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла прогноза: {e}")

    # Читаем leaderboard
    df_leaderboard = None
    if os.path.exists(leaderboard_path):
        try:
            df_leaderboard = pd.read_csv(leaderboard_path)
        except Exception as e:
            logging.warning(f"Не удалось прочитать leaderboard: {e}")
            df_leaderboard = None

    # Читаем параметры обучения
    params_dict = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            params_dict = metadata.get("training_parameters", {})
        except Exception as e:
            logging.warning(f"Не удалось прочитать параметры обучения: {e}")
            params_dict = None

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
                weights_dict = None

    # Формируем новый Excel-файл с несколькими листами
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Первый лист — прогноз
        df_pred.to_excel(writer, sheet_name="Prediction", index=False)
        # Второй лист — leaderboard
        if df_leaderboard is not None:
            df_leaderboard.to_excel(writer, sheet_name="Leaderboard", index=False)
        else:
            pd.DataFrame({"info": ["Leaderboard not found"]}).to_excel(writer, sheet_name="Leaderboard", index=False)
        # Третий лист — параметры обучения
        if params_dict is not None:
            pd.DataFrame(list(params_dict.items()), columns=["Parameter", "Value"]).to_excel(writer, sheet_name="TrainingParams", index=False)
        else:
            pd.DataFrame({"info": ["Training parameters not found"]}).to_excel(writer, sheet_name="TrainingParams", index=False)
        # Четвертый лист — веса WeightedEnsemble
        if weights_dict is not None and isinstance(weights_dict, dict) and len(weights_dict) > 0:
            pd.DataFrame(list(weights_dict.items()), columns=["Model", "Weight"]).to_excel(writer, sheet_name="WeightedEnsemble", index=False)
        else:
            pd.DataFrame({"info": ["WeightedEnsemble weights not found"]}).to_excel(writer, sheet_name="WeightedEnsemble", index=False)
        # Пятый лист — messages из metadata.json
        messages = None
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                messages = metadata.get("messages", None)
            except Exception as e:
                logging.warning(f"Не удалось прочитать messages из metadata.json: {e}")
                messages = None
        if messages and isinstance(messages, list) and len(messages) > 0:
            pd.DataFrame({"messages": messages}).to_excel(writer, sheet_name="Messages", index=False)
        else:
            pd.DataFrame({"info": ["Messages not found"]}).to_excel(writer, sheet_name="Messages", index=False)
    output.seek(0)

    logging.info(f"[download_prediction_file] Мульти-листовой Excel-файл отправлен: prediction_{session_id}.xlsx")
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=prediction_{session_id}.xlsx"
        }
    )

@router.get("/download_prediction_csv/{session_id}")
def download_prediction_csv_file(session_id: str):
    """Скачать ранее сохранённый файл прогноза в формате CSV по id сессии."""
    logging.info(f"[download_prediction_csv_file] Запрос на скачивание csv для session_id={session_id}")
    session_path = get_session_path(session_id)
    prediction_xlsx_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    prediction_csv_path = os.path.join(session_path, f"prediction_{session_id}.csv")
    if not os.path.exists(prediction_xlsx_path):
        logging.error(f"Файл прогноза (xlsx) не найден: {prediction_xlsx_path}")
        raise HTTPException(status_code=404, detail="Файл прогноза не найден")
    # Если CSV уже есть, используем его, иначе конвертируем из xlsx
    if not os.path.exists(prediction_csv_path):
        try:
            df = pd.read_excel(prediction_xlsx_path)
            df.to_csv(prediction_csv_path, index=False, encoding="utf-8-sig")
            logging.info(f"[download_prediction_csv_file] Конвертация xlsx в csv: {prediction_csv_path}")
        except Exception as e:
            logging.error(f"Ошибка при конвертации в CSV: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при конвертации в CSV: {e}")
    with open(prediction_csv_path, "rb") as f:
        file_bytes = f.read()
    logging.info(f"[download_prediction_csv_file] CSV-файл отправлен: {prediction_csv_path}")
    return Response(
        content=file_bytes,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=prediction_{session_id}.csv"
        }
    )
