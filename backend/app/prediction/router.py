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

    # 3. Загружаем обученный предиктор
    model_path = os.path.join(session_path, "model")
    if not os.path.exists(model_path):
        logging.error(f"Папка с моделью не найдена: {model_path}")
        raise HTTPException(status_code=404, detail="Папка с моделью не найдена")
    try:
        predictor = TimeSeriesPredictor.load(model_path)
        logging.info(f"Модель успешно загружена из {model_path}")
    except Exception as e:
        logging.error(f"Ошибка загрузки модели: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки модели: {e}")

    # 4. Загружаем исходный train файл (теперь только parquet)
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

    # 5. Подготовка данных (аналогично обучению)
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

    static_df = None
    if static_feats:
        tmp = df[[id_col] + static_feats].drop_duplicates(subset=[id_col]).copy()
        tmp.rename(columns={id_col: "item_id"}, inplace=True)
        static_df = tmp
        logging.info(f"Добавлены статические признаки: {static_feats}")

    df_ready = convert_to_timeseries(df, id_col, dt_col, tgt_col)
    ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
    if freq and freq.lower() != "auto":
        freq_short = freq.split(" ")[0]
        ts_df = ts_df.convert_frequency(freq_short)
        ts_df = ts_df.fill_missing_values(method="ffill")
        logging.info(f"Частота временного ряда установлена: {freq_short}")

    # 6. Прогноз
    try:
        preds = predictor.predict(ts_df)
        logging.info(f"Прогноз успешно выполнен для session_id={session_id}")
    except Exception as e:
        logging.error(f"Ошибка при прогнозировании: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при прогнозировании: {e}")
    
    return preds

def save_prediction(output, session_id):

    session_path = get_session_path(session_id)
    
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    with open(prediction_file_path, "wb") as f:

        f.write(output.getvalue())
    logging.info(f"[predict_timeseries] Прогноз сохранён в файл: {prediction_file_path}")

@router.get("/predict/{session_id}")
def predict_timeseries_endpoint(session_id: str):
    """Сделать прогноз по id сессии и вернуть xlsx файл с результатом."""
    
    preds = predict_timeseries(session_id)

    output = BytesIO()
    preds.reset_index().to_excel(output, index=False)
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
    """Скачать ранее сохранённый файл прогноза по id сессии."""
    logging.info(f"[download_prediction_file] Запрос на скачивание xlsx для session_id={session_id}")
    session_path = get_session_path(session_id)
    prediction_file_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    if not os.path.exists(prediction_file_path):
        logging.error(f"Файл прогноза не найден: {prediction_file_path}")
        raise HTTPException(status_code=404, detail="Файл прогноза не найден")
    with open(prediction_file_path, "rb") as f:
        file_bytes = f.read()
    logging.info(f"[download_prediction_file] Файл отправлен: {prediction_file_path}")
    return Response(
        content=file_bytes,
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
