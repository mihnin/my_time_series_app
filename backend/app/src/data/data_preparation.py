# src/data/data_preparation.py
import pandas as pd
import logging
from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe

def prepare_timeseries_data(df, dt_col, id_col, tgt_col, 
                          static_feats=None, 
                          use_holidays=False,
                          fill_method="None",
                          group_cols=None):
    """
    Единая функция для подготовки данных временного ряда.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Исходный датафрейм
    dt_col : str
        Название колонки с датами
    id_col : str
        Название колонки с идентификаторами
    tgt_col : str
        Название целевой колонки
    static_feats : list, optional
        Список статических признаков
    use_holidays : bool, optional
        Добавлять ли признак российских праздников
    fill_method : str, optional
        Метод заполнения пропусков
    group_cols : list, optional
        Колонки для группировки при заполнении пропусков
        
    Returns:
    --------
    tuple
        (ts_df, static_df) - подготовленный TimeSeriesDataFrame и статические признаки
    """
    df_copy = df.copy()
    
    # Проверка необходимых колонок
    required_cols = [dt_col, tgt_col, id_col]
    missing_cols = [col for col in required_cols if col not in df_copy.columns]
    if missing_cols:
        raise ValueError(f"Отсутствуют обязательные колонки: {', '.join(missing_cols)}")
    
    # Преобразование даты
    if not pd.api.types.is_datetime64_any_dtype(df_copy[dt_col]):
        df_copy[dt_col] = pd.to_datetime(df_copy[dt_col], errors="coerce")
    
    # Добавление признака праздников
    if use_holidays:
        logging.info("Добавление признака праздников РФ")
        df_copy = add_russian_holiday_feature(df_copy, date_col=dt_col, holiday_col="russian_holiday")
    
    # Заполнение пропусков
    if fill_method != "None":
        logging.info(f"Заполнение пропусков методом {fill_method}")
        df_copy = fill_missing_values(df_copy, method=fill_method, group_cols=group_cols)
    
    # Подготовка статических признаков
    static_df = None
    if static_feats:
        tmp = df_copy[[id_col] + static_feats].drop_duplicates(subset=[id_col]).copy()
        tmp.rename(columns={id_col: "item_id"}, inplace=True)
        static_df = tmp
    
    # Преобразование в TimeSeriesDataFrame
    df_ready = convert_to_timeseries(df_copy, id_col, dt_col, tgt_col)
    ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
    
    return ts_df, static_df