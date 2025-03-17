# src/models/forecasting.py
import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
import pandas as pd

def make_timeseries_dataframe(df, static_features=None, freq='D'):
    """
    Создаёт TimeSeriesDataFrame с улучшенной обработкой ошибок
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм с данными временного ряда.
    static_features : pandas.DataFrame, опционально
        Датафрейм со статическими признаками (постоянными для каждого item_id).
    freq : str, опционально
        Частота временного ряда ('D' по умолчанию для daily)
    
    Returns:
    --------
    TimeSeriesDataFrame
        TimeSeriesDataFrame для использования в AutoGluon.
    """
    from autogluon.timeseries.dataset import TimeSeriesDataFrame
    
    try:
        # Создаем TimeSeriesDataFrame
        ts_df = TimeSeriesDataFrame(df, static_features=static_features)
        
        # Устанавливаем частоту, если указана
        if freq and freq != 'auto':
            try:
                logging.info(f"Устанавливаем частоту {freq} для TimeSeriesDataFrame")
                ts_df = ts_df.convert_frequency(freq=freq)
            except Exception as freq_err:
                logging.warning(f"Не удалось установить частоту {freq}: {freq_err}")
                # Продолжаем с исходной частотой
        
        return ts_df
    except Exception as e:
        logging.error(f"Ошибка при создании TimeSeriesDataFrame: {e}")
        
        # Детальное логирование для отладки
        try:
            logging.debug(f"Форма DataFrame: {df.shape}")
            logging.debug(f"Колонки DataFrame: {df.columns.tolist()}")
            if df.index.name:
                logging.debug(f"Имя индекса: {df.index.name}")
            
            # Проверка требуемых колонок для TimeSeriesDataFrame
            required_cols = ["item_id", "timestamp", "target"]
            for col in required_cols:
                if col not in df.columns:
                    logging.error(f"Отсутствует обязательная колонка: {col}")
                    
            # Проверка типов данных
            if "timestamp" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                logging.error("Колонка timestamp не имеет тип datetime64")
                
            # Проверка наличия пропусков
            if "target" in df.columns:
                num_missing = df["target"].isna().sum()
                if num_missing > 0:
                    missing_percent = 100 * num_missing / len(df)
                    logging.warning(f"В колонке target есть пропуски: {num_missing} ({missing_percent:.2f}%)")
                    
            # Проверка наличия дубликатов
            if "item_id" in df.columns and "timestamp" in df.columns:
                duplicate_pairs = df.duplicated(subset=["item_id", "timestamp"]).sum()
                if duplicate_pairs > 0:
                    logging.error(f"Найдены дубликаты в парах item_id-timestamp: {duplicate_pairs}")
                
        except Exception as debug_err:
            logging.error(f"Ошибка при отладочном логировании: {debug_err}")
        
        raise ValueError(f"Не удалось создать TimeSeriesDataFrame: {e}")

def forecast(predictor: TimeSeriesPredictor, ts_df, known_covariates=None):
    """
    Вызывает predictor.predict() и возвращает прогноз.
    """
    logging.info("Вызов predictor.predict()...")
    preds = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return preds








