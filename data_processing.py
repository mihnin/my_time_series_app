import pandas as pd
import os
import logging
import streamlit as st

def load_data(uploaded_file):
    """
    Загружает данные из локального CSV/Excel файла, загруженного через Streamlit.
    """
    if uploaded_file is None:
        raise ValueError("Файл не выбран (uploaded_file is None).")

    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    logging.info(f"Попытка загрузить пользовательский файл: {uploaded_file.name}")

    if file_extension == '.csv':
        df = pd.read_csv(uploaded_file)
    elif file_extension in ['.xls', '.xlsx']:
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Неподдерживаемый формат файла. Используйте CSV или Excel.")

    logging.info(f"Успешно загружено {len(df)} записей из {uploaded_file.name}")
    return df


def convert_to_timeseries(df, id_col, timestamp_col, target_col, static_df=None) -> pd.DataFrame:
    """
    Преобразует DataFrame так, чтобы в итоге были колонки: 
      'item_id', 'timestamp', 'target'.
    """
    required_columns = {id_col, timestamp_col, target_col}
    missing_cols = required_columns - set(df.columns)
    if missing_cols:
        msg = f"Отсутствуют обязательные колонки: {missing_cols}"
        logging.error(msg)
        raise ValueError(msg + ". Проверьте названия столбцов.")

    df = df.rename(columns={
        id_col: "item_id",
        timestamp_col: "timestamp",
        target_col: "target"
    })

    # Заполняем пропуски в target
    if df["target"].isnull().any():
        st.warning("⚠️ Пропущенные значения в целевой переменной. Заполняем медианой по каждой серии (item_id).")
        df["target"] = df.groupby("item_id")["target"].transform(
            lambda x: x.fillna(x.median())
        )

    # Преобразуем timestamp в datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
    if df["timestamp"].isnull().any():
        invalid_dates = df[df["timestamp"].isnull()]
        msg = (
            f"Некорректные значения даты в строках: {invalid_dates.index.tolist()}. "
            f"Проверьте формат даты или исправьте/удалите неверные значения."
        )
        logging.error(msg)
        raise ValueError(msg)

    # Сортируем
    df = df.sort_values(by=["item_id", "timestamp"])

    # Проверка дубликатов
    duplicates = df.duplicated(subset=["item_id", "timestamp"], keep=False)
    if duplicates.any():
        msg = (
            f"Обнаружены дубликаты (item_id, timestamp) в строках: {df[duplicates].index.tolist()}. "
            f"Удалите или объедините дубликаты."
        )
        logging.error(msg)
        raise ValueError(msg)

    # Статические признаки, если есть
    if static_df is not None:
        df = df.merge(static_df, on="item_id", how='left')

    return df





