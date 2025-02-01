# src/models/forecasting.py
import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def make_timeseries_dataframe(df, static_df=None):
    """
    Создаёт TimeSeriesDataFrame из df с указанными столбцами.
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
    Вызывает predictor.predict() и возвращает прогноз.
    """
    logging.info("Вызов predictor.predict()...")
    preds = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return preds








