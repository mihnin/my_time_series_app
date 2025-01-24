import logging
from autogluon.timeseries import TimeSeriesDataFrame
from autogluon.timeseries import TimeSeriesPredictor
#test

def make_timeseries_dataframe(df, static_df=None):
    """
    Создаёт TimeSeriesDataFrame из pandas DataFrame, где колонки: item_id, timestamp, target.
    При необходимости, подключает static_df (статические фичи).
    """
    ts_df = TimeSeriesDataFrame.from_data_frame(
        df,
        id_column="item_id",
        timestamp_column="timestamp",
        static_features_df=static_df  # Если есть словарь {item_id -> static feats}
    )
    return ts_df

def forecast(predictor, ts_df, known_covariates=None):
    """
    Выполняет прогноз и возвращает DataFrame (MultiIndex: item_id, timestamp).
    Колонки по умолчанию — квантильные (0.1, 0.2, 0.3...).
    """
    logging.info("Вызов predictor.predict()...")
    predictions = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return predictions



