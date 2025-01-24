import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def make_timeseries_dataframe(df, static_df=None):
    """
    Создаёт TimeSeriesDataFrame из pandas DataFrame (item_id, timestamp, target).
    При необходимости прикрепляет static_features_df (со столбцом "item_id").
    """
    ts_df = TimeSeriesDataFrame.from_data_frame(
        df,
        id_column="item_id",
        timestamp_column="timestamp",
        static_features_df=static_df
    )
    return ts_df

def forecast(predictor: TimeSeriesPredictor, ts_df, known_covariates=None):
    """
    Выполняет прогноз. Возвращает DataFrame (MultiIndex: (item_id, timestamp)).
    Колонки — квантильные (0.1, 0.2, ..., 0.9) или среднее (0.5), если mean_only=True.
    """
    logging.info("Вызов predictor.predict()...")
    preds = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return preds



