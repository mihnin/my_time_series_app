import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

def make_timeseries_dataframe(df, static_df=None):
    """
    Создаёт TimeSeriesDataFrame из pandas DataFrame, где уже есть item_id/timestamp/target.
    """
    ts_df = TimeSeriesDataFrame.from_data_frame(
        df,
        id_column="item_id",
        timestamp_column="timestamp",
        static_features_df=static_df
    )
    return ts_df


def train_model(
    train_ts_df,
    target,
    prediction_length,
    time_limit,
    presets,
    eval_metric,
    known_covariates=None,
    hyperparameters=None
):
    """
    Обучает TimeSeriesPredictor с учётом (опционального) hyperparameters,
    чтобы ограничить модели только выбранными пользователем.
    """
    logging.info("Инициализация TimeSeriesPredictor...")
    predictor = TimeSeriesPredictor(
        target=target, 
        prediction_length=prediction_length,
        eval_metric=eval_metric,
        known_covariates_names=known_covariates if known_covariates else None
    )
    logging.info(
        f"Начало fit() с time_limit={time_limit}, presets={presets}, eval_metric={eval_metric}, "
        f"hyperparameters={hyperparameters}"
    )

    predictor.fit(
        train_data=train_ts_df,
        time_limit=time_limit,
        presets=presets,
        hyperparameters=hyperparameters
    )
    logging.info("Обучение модели завершено.")
    return predictor


def forecast(predictor, ts_df, known_covariates=None):
    """
    Выполняет прогноз и возвращает DataFrame, индекс=MultiIndex(item_id, timestamp).
    Колонки по умолчанию — квантильные (0.1, 0.2, 0.3...).
    """
    logging.info("Вызов predictor.predict()...")
    predictions = predictor.predict(ts_df, known_covariates=known_covariates)
    logging.info("Прогнозирование завершено.")
    return predictions


