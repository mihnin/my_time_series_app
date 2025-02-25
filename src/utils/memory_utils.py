# src/utils/memory_utils.py (новый файл)
import gc
import psutil
import logging
import pandas as pd

def get_memory_usage_mb():
    """Возвращает текущее использование памяти процессом в МБ"""
    process = psutil.Process()
    memory_info = process.memory_info()
    return memory_info.rss / (1024 * 1024)

def optimize_dataframe(df, categorical_threshold=10):
    """
    Оптимизирует использование памяти DataFrame путем преобразования типов данных.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Исходный датафрейм для оптимизации
    categorical_threshold : int, optional
        Порог уникальных значений для преобразования в категориальный тип
        
    Returns:
    --------
    pandas.DataFrame
        Оптимизированный датафрейм
    """
    result = df.copy()
    
    # Оптимизация целочисленных колонок
    int_cols = result.select_dtypes(include=['int']).columns
    for col in int_cols:
        result[col] = pd.to_numeric(result[col], downcast='integer')
    
    # Оптимизация колонок с плавающей точкой
    float_cols = result.select_dtypes(include=['float']).columns
    for col in float_cols:
        result[col] = pd.to_numeric(result[col], downcast='float')
    
    # Преобразование строковых колонок с небольшим числом уникальных значений в категории
    object_cols = result.select_dtypes(include=['object']).columns
    for col in object_cols:
        num_unique = result[col].nunique()
        if num_unique < categorical_threshold:
            result[col] = result[col].astype('category')
    
    # Журналирование результатов оптимизации
    before_size = df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
    after_size = result.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
    savings = before_size - after_size
    logging.info(f"Оптимизация DataFrame: {before_size:.2f} МБ -> {after_size:.2f} МБ (экономия: {savings:.2f} МБ)")
    
    return result

def clean_memory(verbose=True):
    """
    Принудительно запускает сборщик мусора и освобождает неиспользуемую память.
    
    Parameters:
    -----------
    verbose : bool, optional
        Выводить ли информацию о памяти до и после очистки
        
    Returns:
    --------
    float
        Количество освобожденной памяти в МБ
    """
    before = get_memory_usage_mb()
    
    # Запускаем сборщик мусора
    gc.collect()
    
    after = get_memory_usage_mb()
    freed = before - after
    
    if verbose:
        logging.info(f"Очистка памяти: {before:.2f} МБ -> {after:.2f} МБ (освобождено: {freed:.2f} МБ)")
    
    return freed