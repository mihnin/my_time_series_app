# src/models/forecasting.py
import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def make_timeseries_dataframe(df, static_features=None, freq='D'):
    """
    Создаёт TimeSeriesDataFrame из pandas DataFrame с учетом статических признаков.
    
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
        ts_df = TimeSeriesDataFrame(df, static_features=static_features, freq=freq)
        return ts_df
    except Exception as e:
        logging.error(f"Ошибка при создании TimeSeriesDataFrame: {e}")
        
        # Пробуем создать без указания частоты, если это вызвало проблему
        try:
            logging.warning(f"Пробуем создать TimeSeriesDataFrame без указания частоты")
            ts_df = TimeSeriesDataFrame(df, static_features=static_features)
            return ts_df
        except Exception as e2:
            logging.error(f"Повторная ошибка при создании TimeSeriesDataFrame: {e2}")
            raise ValueError(f"Не удалось создать TimeSeriesDataFrame: {e2}")

def forecast(predictor: TimeSeriesPredictor, ts_df, known_covariates=None):
    """
    Вызывает predictor.predict() и возвращает прогноз.
    """
    logging.info("Вызов predictor.predict()...")
    preds = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return preds








