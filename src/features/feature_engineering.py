import pandas as pd
import streamlit as st
import holidays
import logging

def fill_missing_values(df: pd.DataFrame, method: str = "None", group_cols=None) -> pd.DataFrame:
    """
    Заполняет пропуски (только для числовых столбцов).
      - "Constant=0": NaN -> 0
      - "Forward fill": ffill/bfill
      - "Group mean": fillna средним в группе
      - "None": не трогаем
    """
    numeric_cols = df.select_dtypes(include=["float", "int"]).columns

    if not group_cols:
        group_cols = []

    if len(group_cols) == 1:
        group_cols = (group_cols[0],)  # убрать предупреждение pandas

    if method == "None":
        return df
    elif method == "Constant=0":
        df[numeric_cols] = df[numeric_cols].fillna(0)
        return df
    elif method == "Forward fill":
        if group_cols:
            df = df.sort_values(by=group_cols, na_position="last")
            df[numeric_cols] = df.groupby(group_cols)[numeric_cols].transform(lambda g: g.ffill().bfill())
        else:
            df[numeric_cols] = df[numeric_cols].ffill().bfill()
        return df
    elif method == "Group mean":
        if group_cols:
            df = df.sort_values(by=group_cols, na_position="last")
            for c in numeric_cols:
                df[c] = df.groupby(group_cols)[c].transform(lambda x: x.fillna(x.mean()))
        else:
            for c in numeric_cols:
                df[c] = df[c].fillna(df[c].mean())
        return df

    return df

def add_russian_holiday_feature(df: pd.DataFrame, date_col="timestamp", holiday_col="russian_holiday") -> pd.DataFrame:
    """
    Добавляет колонку holiday_col (0 или 1) для праздников РФ (дату берем из date_col).
    """
    if date_col not in df.columns:
        st.warning("Колонка даты не найдена, не можем добавить признак праздника.")
        return df
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    min_year = df[date_col].dt.year.min()
    max_year = df[date_col].dt.year.max()

    ru_holidays = holidays.country_holidays(country="RU", years=range(min_year, max_year + 1))

    def is_holiday(dt):
        return 1.0 if dt.date() in ru_holidays else 0.0

    df[holiday_col] = df[date_col].apply(is_holiday).astype(float)
    return df




