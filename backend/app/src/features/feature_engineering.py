#feature_engineering.py
# src/features/feature_engineering.py
import pandas as pd
import streamlit as st
import holidays
import logging
import numpy as np
from typing import List, Optional, Union, Dict, Any
from scipy import stats

def fill_missing_values(df: pd.DataFrame, method: str = "None", group_cols=None) -> pd.DataFrame:
    """
    Заполняет пропуски для числовых столбцов.
    """
    numeric_cols = df.select_dtypes(include=["float", "int"]).columns
    if not group_cols:
        group_cols = []
    if len(group_cols) == 1:
        group_cols = (group_cols[0],)
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
    elif method == "Interpolate":
        if group_cols:
            df = df.sort_values(by=group_cols, na_position="last")
            for group, group_df in df.groupby(group_cols):
                df.loc[group_df.index, numeric_cols] = group_df[numeric_cols].interpolate(method='linear')
        else:
            df[numeric_cols] = df[numeric_cols].interpolate(method='linear')
        return df
    elif method == "KNN imputer":
        try:
            from sklearn.impute import KNNImputer
            imputer = KNNImputer(n_neighbors=5)
            
            if group_cols:
                df = df.sort_values(by=group_cols, na_position="last")
                for group, group_df in df.groupby(group_cols):
                    if group_df[numeric_cols].isnull().values.any():
                        # Если есть пропуски в группе
                        imputed_values = imputer.fit_transform(group_df[numeric_cols])
                        df.loc[group_df.index, numeric_cols] = imputed_values
            else:
                if df[numeric_cols].isnull().values.any():
                    # Если есть пропуски
                    imputed_values = imputer.fit_transform(df[numeric_cols])
                    df[numeric_cols] = imputed_values
            
            return df
        except Exception as e:
            logging.error(f"Ошибка при использовании KNN imputer: {e}")
            st.warning(f"Не удалось применить KNN imputer: {e}. Используем Forward fill.")
            return fill_missing_values(df, method="Forward fill", group_cols=group_cols)
    
    return df

def add_russian_holiday_feature(df: pd.DataFrame, date_col="timestamp", holiday_col="russian_holiday") -> pd.DataFrame:
    """
    Добавляет колонку с индикатором праздников РФ.
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

def add_time_features(df: pd.DataFrame, 
                     date_col: str, 
                     features: List[str] = None) -> pd.DataFrame:
    """
    Добавляет временные признаки к датафрейму.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    date_col : str
        Название колонки с датами
    features : List[str]
        Список временных признаков для добавления:
        - 'year', 'month', 'day', 'dayofweek', 'quarter', 'hour', 'minute'
        - 'is_weekend', 'is_month_start', 'is_month_end'
        - 'sin_month', 'cos_month', 'sin_day', 'cos_day'
        
    Returns:
    --------
    pd.DataFrame
        Датафрейм с добавленными временными признаками
    """
    if date_col not in df.columns:
        st.warning(f"Колонка {date_col} не найдена в датафрейме.")
        return df
    
    # Преобразуем к формату datetime, если необходимо
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    
    # Создаем копию для добавления новых признаков
    df_result = df.copy()
    
    # Если не указаны конкретные признаки, добавляем все
    if features is None:
        features = ['year', 'month', 'day', 'dayofweek', 'quarter', 'is_weekend',
                   'is_month_start', 'is_month_end', 'sin_month', 'cos_month']
    
    # Добавляем базовые признаки
    if 'year' in features:
        df_result['year'] = df_result[date_col].dt.year
    
    if 'month' in features:
        df_result['month'] = df_result[date_col].dt.month
    
    if 'day' in features:
        df_result['day'] = df_result[date_col].dt.day
    
    if 'dayofweek' in features:
        df_result['dayofweek'] = df_result[date_col].dt.dayofweek
    
    if 'quarter' in features:
        df_result['quarter'] = df_result[date_col].dt.quarter
    
    if 'hour' in features:
        df_result['hour'] = df_result[date_col].dt.hour
    
    if 'minute' in features:
        df_result['minute'] = df_result[date_col].dt.minute
    
    # Добавляем флаги
    if 'is_weekend' in features:
        df_result['is_weekend'] = (df_result[date_col].dt.dayofweek >= 5).astype(int)
    
    if 'is_month_start' in features:
        df_result['is_month_start'] = df_result[date_col].dt.is_month_start.astype(int)
    
    if 'is_month_end' in features:
        df_result['is_month_end'] = df_result[date_col].dt.is_month_end.astype(int)
    
    # Добавляем циклические признаки
    if 'sin_month' in features:
        df_result['sin_month'] = np.sin(2 * np.pi * df_result[date_col].dt.month / 12)
    
    if 'cos_month' in features:
        df_result['cos_month'] = np.cos(2 * np.pi * df_result[date_col].dt.month / 12)
    
    if 'sin_day' in features:
        df_result['sin_day'] = np.sin(2 * np.pi * df_result[date_col].dt.day / 31)
    
    if 'cos_day' in features:
        df_result['cos_day'] = np.cos(2 * np.pi * df_result[date_col].dt.day / 31)
    
    if 'sin_dayofweek' in features:
        df_result['sin_dayofweek'] = np.sin(2 * np.pi * df_result[date_col].dt.dayofweek / 7)
    
    if 'cos_dayofweek' in features:
        df_result['cos_dayofweek'] = np.cos(2 * np.pi * df_result[date_col].dt.dayofweek / 7)
    
    return df_result

def apply_target_transformations(df: pd.DataFrame, 
                               target_col: str, 
                               transformation: str = None, 
                               inverse: bool = False) -> pd.DataFrame:
    """
    Применяет трансформации к целевой переменной.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    target_col : str
        Название целевой колонки
    transformation : str
        Тип трансформации:
        - 'log' - логарифмическая (log(x+1))
        - 'sqrt' - корень квадратный
        - 'box-cox' - преобразование Бокса-Кокса
        - 'yeo-johnson' - преобразование Йео-Джонсона
    inverse : bool
        Если True, применяется обратное преобразование
        
    Returns:
    --------
    pd.DataFrame
        Датафрейм с трансформированной целевой переменной
    """
    if target_col not in df.columns:
        st.warning(f"Колонка {target_col} не найдена в датафрейме.")
        return df
    
    df_result = df.copy()
    
    if not inverse:
        # Прямое преобразование
        if transformation == 'log':
            # Логарифмическое преобразование (log(x+1))
            df_result[target_col] = np.log1p(df_result[target_col])
            
        elif transformation == 'sqrt':
            # Корень квадратный
            df_result[target_col] = np.sqrt(df_result[target_col])
            
        elif transformation == 'box-cox':
            # Преобразование Бокса-Кокса (только для положительных значений)
            if (df_result[target_col] <= 0).any():
                min_val = df_result[target_col].min()
                if min_val <= 0:
                    shift = abs(min_val) + 1
                    df_result[target_col] = df_result[target_col] + shift
                    st.info(f"Добавлено смещение {shift} к целевой переменной для Box-Cox трансформации.")
            
            transformed_data, lambda_value = stats.boxcox(df_result[target_col])
            df_result[target_col] = transformed_data
            
            # Сохраняем лямбда параметр
            df_result.attrs['box_cox_lambda'] = lambda_value
            df_result.attrs['box_cox_shift'] = locals().get('shift', 0)
            
        elif transformation == 'yeo-johnson':
            # Преобразование Йео-Джонсона (работает с любыми значениями)
            transformed_data, lambda_value = stats.yeojohnson(df_result[target_col])
            df_result[target_col] = transformed_data
            
            # Сохраняем лямбда параметр
            df_result.attrs['yeo_johnson_lambda'] = lambda_value
    
    else:
        # Обратное преобразование
        if transformation == 'log':
            # Обратное логарифмическое преобразование (exp(x)-1)
            df_result[target_col] = np.expm1(df_result[target_col])
            
        elif transformation == 'sqrt':
            # Обратное преобразование корня квадратного
            df_result[target_col] = np.square(df_result[target_col])
            
        elif transformation == 'box-cox':
            # Обратное преобразование Бокса-Кокса
            if 'box_cox_lambda' not in df_result.attrs:
                raise ValueError("Параметр лямбда для обратного преобразования Box-Cox не найден.")
            
            lambda_value = df_result.attrs['box_cox_lambda']
            shift = df_result.attrs.get('box_cox_shift', 0)
            
            df_result[target_col] = stats.inv_boxcox(df_result[target_col], lambda_value)
            
            # Уменьшаем на величину смещения, если оно было применено
            if shift > 0:
                df_result[target_col] = df_result[target_col] - shift
            
        elif transformation == 'yeo-johnson':
            # Обратное преобразование Йео-Джонсона
            if 'yeo_johnson_lambda' not in df_result.attrs:
                raise ValueError("Параметр лямбда для обратного преобразования Yeo-Johnson не найден.")
            
            lambda_value = df_result.attrs['yeo_johnson_lambda']
            df_result[target_col] = stats.inv_yeojohnson(df_result[target_col], lambda_value)
    
    return df_result

def generate_lag_features(df: pd.DataFrame, 
                         target_col: str, 
                         date_col: str,
                         id_col: Optional[str] = None,
                         lag_periods: List[int] = [1, 7, 14, 28]) -> pd.DataFrame:
    """
    Создает признаки запаздывания (лаги) для временного ряда.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    target_col : str
        Название целевой колонки
    date_col : str
        Название колонки с датами
    id_col : str, optional
        Название колонки с идентификаторами
    lag_periods : List[int]
        Список периодов запаздывания
        
    Returns:
    --------
    pd.DataFrame
        Датафрейм с добавленными лаговыми признаками
    """
    # Преобразуем к формату datetime, если необходимо
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    
    df_result = df.copy()
    
    # Сортируем по дате
    if id_col and id_col in df.columns:
        df_result = df_result.sort_values([id_col, date_col])
    else:
        df_result = df_result.sort_values(date_col)
    
    # Создаем лаговые признаки
    for lag in lag_periods:
        lag_col_name = f'{target_col}_lag_{lag}'
        
        if id_col and id_col in df.columns:
            # Для каждого ID создаем отдельный лаг
            df_result[lag_col_name] = df_result.groupby(id_col)[target_col].shift(lag)
        else:
            # Создаем лаг для всего ряда
            df_result[lag_col_name] = df_result[target_col].shift(lag)
    
    return df_result

def generate_rolling_features(df: pd.DataFrame, 
                            target_col: str, 
                            date_col: str,
                            id_col: Optional[str] = None,
                            windows: List[int] = [7, 14, 30],
                            functions: List[str] = ['mean', 'std', 'min', 'max']) -> pd.DataFrame:
    """
    Создает скользящие (rolling) признаки для временного ряда.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    target_col : str
        Название целевой колонки
    date_col : str
        Название колонки с датами
    id_col : str, optional
        Название колонки с идентификаторами
    windows : List[int]
        Список размеров окон для скользящих признаков
    functions : List[str]
        Список функций для скользящих признаков ('mean', 'std', 'min', 'max', etc.)
        
    Returns:
    --------
    pd.DataFrame
        Датафрейм с добавленными скользящими признаками
    """
    # Преобразуем к формату datetime, если необходимо
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    
    df_result = df.copy()
    
    # Сортируем по дате
    if id_col and id_col in df.columns:
        df_result = df_result.sort_values([id_col, date_col])
    else:
        df_result = df_result.sort_values(date_col)
    
    # Создаем скользящие признаки
    for window in windows:
        for func in functions:
            feat_name = f'{target_col}_rolling_{window}_{func}'
            
            if id_col and id_col in df.columns:
                # Для каждого ID создаем отдельные скользящие признаки
                if func == 'mean':
                    df_result[feat_name] = df_result.groupby(id_col)[target_col].transform(
                        lambda x: x.rolling(window=window, min_periods=1).mean()
                    )
                elif func == 'std':
                    df_result[feat_name] = df_result.groupby(id_col)[target_col].transform(
                        lambda x: x.rolling(window=window, min_periods=1).std()
                    )
                elif func == 'min':
                    df_result[feat_name] = df_result.groupby(id_col)[target_col].transform(
                        lambda x: x.rolling(window=window, min_periods=1).min()
                    )
                elif func == 'max':
                    df_result[feat_name] = df_result.groupby(id_col)[target_col].transform(
                        lambda x: x.rolling(window=window, min_periods=1).max()
                    )
            else:
                # Создаем скользящие признаки для всего ряда
                if func == 'mean':
                    df_result[feat_name] = df_result[target_col].rolling(window=window, min_periods=1).mean()
                elif func == 'std':
                    df_result[feat_name] = df_result[target_col].rolling(window=window, min_periods=1).std()
                elif func == 'min':
                    df_result[feat_name] = df_result[target_col].rolling(window=window, min_periods=1).min()
                elif func == 'max':
                    df_result[feat_name] = df_result[target_col].rolling(window=window, min_periods=1).max()
    
    return df_result
