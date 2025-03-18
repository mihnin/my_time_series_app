# src/data/auto_detect.py
import pandas as pd
import numpy as np
import logging
import re
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timedelta

from src.config.app_config import get_config

def detect_field_types(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Определяет типы полей в датафрейме (даты, числовые, категориальные)
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм с данными
        
    Returns:
    --------
    Dict[str, Dict[str, Any]]
        Словарь с категориями полей и их свойствами
    """
    config = get_config()
    fields_info = {
        'datetime': [],      # колонки с датами
        'numeric': [],       # числовые колонки
        'categorical': [],   # категориальные колонки
        'text': [],          # текстовые колонки
        'binary': [],        # бинарные колонки (0/1)
        'other': []          # прочие колонки
    }
    
    field_properties = {}  # свойства каждой колонки
    
    # Настройки автоопределения
    auto_detection_config = config.get('auto_detection', {})
    date_formats = auto_detection_config.get('date_formats', [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%d.%m.%Y %H:%M:%S"
    ])
    
    # Перебираем все колонки
    for col in df.columns:
        col_info = {
            'name': col,
            'dtype': str(df[col].dtype),
            'nunique': df[col].nunique(),
            'missing': df[col].isna().sum(),
            'missing_pct': df[col].isna().mean() * 100
        }
        
        # Определяем тип колонки
        if pd.api.types.is_numeric_dtype(df[col]):
            # Числовая колонка
            col_info['min'] = df[col].min()
            col_info['max'] = df[col].max()
            col_info['mean'] = df[col].mean()
            col_info['std'] = df[col].std()
            
            # Проверяем, может быть это бинарная переменная
            if set(df[col].dropna().unique()).issubset({0, 1}):
                fields_info['binary'].append(col)
            else:
                fields_info['numeric'].append(col)
        
        elif pd.api.types.is_datetime64_dtype(df[col]):
            # Уже распознанная дата
            fields_info['datetime'].append(col)
            col_info['min_date'] = df[col].min()
            col_info['max_date'] = df[col].max()
        
        else:
            # Пробуем конвертировать в дату
            is_date = False
            
            # Если колонка похожа на дату по имени
            date_patterns = auto_detection_config.get('date_column_patterns', ['date', 'дата', 'time', 'время'])
            
            if any(pattern.lower() in col.lower() for pattern in date_patterns) or 'date' in col.lower():
                # Пробуем распознать как дату
                for date_format in date_formats:
                    try:
                        # Пробуем преобразовать в дату
                        dates = pd.to_datetime(df[col], format=date_format, errors='raise')
                        df[col] = dates  # Заменяем в датафрейме
                        fields_info['datetime'].append(col)
                        col_info['min_date'] = dates.min()
                        col_info['max_date'] = dates.max()
                        is_date = True
                        logging.info(f"Колонка {col} успешно преобразована в дату с форматом {date_format}")
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Если не дата, то определяем категориальная или текстовая
            if not is_date:
                if not pd.api.types.is_string_dtype(df[col]) and not pd.api.types.is_object_dtype(df[col]):
                    fields_info['other'].append(col)
                elif df[col].nunique() < min(20, len(df) * 0.1):  # Если мало уникальных значений
                    fields_info['categorical'].append(col)
                else:
                    fields_info['text'].append(col)

        field_properties[col] = col_info
    
    return {
        'fields_by_type': fields_info,
        'field_properties': field_properties
    }

def detect_column_names(df: pd.DataFrame) -> Dict[str, str]:
    """
    Автоматически определяет колонки для даты, ID и target
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм с данными
        
    Returns:
    --------
    Dict[str, str]
        Словарь с определенными колонками
    """
    # Определяем типы полей
    field_detection = detect_field_types(df)
    fields_by_type = field_detection['fields_by_type']
    
    config = get_config()
    auto_detection_config = config.get('auto_detection', {})
    
    # Шаблоны для поиска колонок
    date_patterns = auto_detection_config.get('date_column_patterns', 
        ['date', 'дата', 'time', 'время', 'период'])
    id_patterns = auto_detection_config.get('id_column_patterns', 
        ['id', 'код', 'индекс', 'артикул', 'категория'])
    target_patterns = auto_detection_config.get('target_column_patterns', 
        ['target', 'цель', 'значение', 'продажи', 'спрос'])
    
    # Результаты
    result = {
        'dt_col': None,
        'id_col': None,
        'tgt_col': None
    }
    
    # 1. Ищем колонку с датой
    if fields_by_type['datetime']:
        # Найти дату по шаблону или взять первую
        for pattern in date_patterns:
            date_cols_matched = [col for col in fields_by_type['datetime'] 
                                if pattern.lower() in col.lower()]
            if date_cols_matched:
                result['dt_col'] = date_cols_matched[0]
                break
        
        # Если по шаблону не нашли, берем первую дату
        if not result['dt_col'] and fields_by_type['datetime']:
            result['dt_col'] = fields_by_type['datetime'][0]
    
    # 2. Ищем колонку с ID
    if fields_by_type['categorical']:
        # Найти ID по шаблону
        for pattern in id_patterns:
            id_cols_matched = [col for col in fields_by_type['categorical'] 
                             if pattern.lower() in col.lower()]
            if id_cols_matched:
                result['id_col'] = id_cols_matched[0]
                break
        
        # Если по шаблону не нашли, берем категориальную колонку с умеренным кол-вом уникальных значений
        if not result['id_col'] and fields_by_type['categorical']:
            # Выбираем колонку с разумным кол-вом категорий (2-100)
            for col in fields_by_type['categorical']:
                n_unique = df[col].nunique()
                if 2 <= n_unique <= 100:
                    result['id_col'] = col
                    break
    
    # 3. Ищем целевую колонку
    if fields_by_type['numeric']:
        # Найти таргет по шаблону
        for pattern in target_patterns:
            target_cols_matched = [col for col in fields_by_type['numeric'] 
                                 if pattern.lower() in col.lower()]
            if target_cols_matched:
                result['tgt_col'] = target_cols_matched[0]
                break
        
        # Если по шаблону не нашли, берем первую числовую
        if not result['tgt_col'] and fields_by_type['numeric']:
            result['tgt_col'] = fields_by_type['numeric'][0]
    
    logging.info(f"Автоматически определены колонки: dt_col={result['dt_col']}, " 
                f"id_col={result['id_col']}, tgt_col={result['tgt_col']}")
    
    return result

def detect_frequency(df: pd.DataFrame, date_col: str, id_col: Optional[str] = None) -> str:
    """
    Определяет частоту временного ряда на основе интервалов между точками
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм с данными
    date_col : str
        Название колонки с датой
    id_col : str, optional
        Название колонки с ID (если есть)
        
    Returns:
    --------
    str
        Определенная частота ('H', 'D', 'W', 'M', 'Q', 'Y')
    """
    config = get_config()
    frequency_enabled = config.get('auto_detection', {}).get('frequency_enabled', True)
    
    if not frequency_enabled:
        return 'auto'
    
    # Проверяем, что колонки существуют
    if date_col not in df.columns:
        logging.warning(f"Колонка {date_col} не найдена в датафрейме")
        return 'auto'
    
    if id_col and id_col not in df.columns:
        logging.warning(f"Колонка {id_col} не найдена в датафрейме")
        id_col = None
    
    # Убеждаемся, что колонка даты имеет правильный тип
    try:
        if not pd.api.types.is_datetime64_dtype(df[date_col]):
            df[date_col] = pd.to_datetime(df[date_col])
    except Exception as e:
        logging.error(f"Ошибка при преобразовании {date_col} в дату: {e}")
        return 'auto'
    
    # Сортируем данные по дате
    df_sorted = df.sort_values(date_col)
    
    frequency_intervals = []
    
    if id_col:
        # Если есть ID, вычисляем разницу для каждого ID отдельно
        for group_id, group_df in df_sorted.groupby(id_col):
            if len(group_df) >= 2:  # Нужно минимум 2 точки
                # Вычисляем разницу между последовательными датами
                date_diffs = group_df[date_col].diff().dropna()
                frequency_intervals.extend(date_diffs.dt.total_seconds() / (24 * 3600))  # в днях
    else:
        # Вычисляем разницу между последовательными датами для всего датафрейма
        date_diffs = df_sorted[date_col].diff().dropna()
        frequency_intervals = date_diffs.dt.total_seconds() / (24 * 3600)  # в днях
    
    # Если нет данных, возвращаем auto
    if not frequency_intervals:
        return 'auto'
    
    # Вычисляем среднее и медиану интервалов
    mean_interval = np.mean(frequency_intervals)
    median_interval = np.median(frequency_intervals)
    
    # Можно использовать медиану для более устойчивых результатов
    interval_days = median_interval
    
    # Получаем пороги из конфигурации
    thresholds = config.get('auto_detection', {}).get('frequency_thresholds', {
        'month': 28, 'week': 6, 'day': 0.9, 'hour': 0.04
    })
    
    # Определяем частоту на основе интервала
    if interval_days < thresholds.get('hour', 0.04):  # < ~1 час
        frequency = 'h'
    elif interval_days < thresholds.get('day', 0.9):  # < ~1 день
        frequency = 'D'
    elif interval_days < thresholds.get('week', 6):  # < ~1 неделя
        frequency = 'W'
    elif interval_days < thresholds.get('month', 28):  # < ~1 месяц
        frequency = 'ME'  # Используем 'ME' (месяц, конец) вместо устаревшего 'M'
    elif interval_days < 90:  # < ~3 месяца
        frequency = 'Q'
    else:
        frequency = 'Y'
    
    logging.info(f"Определена частота данных: {frequency} (средний интервал = {mean_interval:.2f} дней)")
    
    return frequency 