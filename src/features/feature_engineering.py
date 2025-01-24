import pandas as pd
import streamlit as st
import logging
import holidays

def fill_missing_values(df: pd.DataFrame, method: str = "None", group_cols=None) -> pd.DataFrame:
    """
    Выполняет заполнение пропусков (только для числовых столбцов).
    - "Constant=0": для float/int -> 0
    - "Group mean": groupby(group_cols) и fillna(mean)
    - "Forward fill": ffill/bfill (при желании, внутри групп)
    - "None": не трогаем
    """
    numeric_cols = df.select_dtypes(include=["float", "int"]).columns
    if method == "None":
        return df
    elif method == "Constant=0":
        df[numeric_cols] = df[numeric_cols].fillna(0)
    elif method == "Forward fill":
        if group_cols:
            df = df.sort_values(by=group_cols, na_position="last")
            df[numeric_cols] = df.groupby(group_cols)[numeric_cols].apply(lambda g: g.ffill().bfill())
        else:
            df[numeric_cols] = df[numeric_cols].ffill().bfill()
    elif method == "Group mean":
        if not group_cols:
            for c in numeric_cols:
                df[c] = df[c].fillna(df[c].mean())
        else:
            df = df.sort_values(by=group_cols, na_position="last")
            for c in numeric_cols:
                df[c] = df.groupby(group_cols)[c].apply(lambda g: g.fillna(g.mean()))
    return df

def add_russian_holiday_feature(df: pd.DataFrame, date_col="timestamp", holiday_col="russian_holiday") -> pd.DataFrame:
    """
    Добавляет бинарный признак праздников РФ (1 = праздник, 0 = нет).
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
