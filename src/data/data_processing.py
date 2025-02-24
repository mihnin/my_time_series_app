# src/data/data_processing.py
import pandas as pd
import logging
import streamlit as st
from pathlib import Path
from io import StringIO
import numpy as np
from typing import Optional, Tuple

def load_data(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, 
             chunk_size: Optional[int] = None) -> pd.DataFrame:
    """
    Загружает данные из CSV/Excel файла с оптимизацией для больших файлов.
    
    Parameters:
    -----------
    uploaded_file : st.runtime.uploaded_file_manager.UploadedFile
        Загруженный пользователем файл
    chunk_size : int, optional
        Размер чанка для обработки больших файлов (в строках)
        
    Returns:
    --------
    pd.DataFrame
        Загруженные данные
    """
    if not uploaded_file:
        logging.error("Попытка загрузки без выбора файла")
        raise ValueError("Ошибка: Файл не выбран!")

    file_ext = Path(uploaded_file.name).suffix.lower()
    file_size_mb = uploaded_file.size / (1024 * 1024)
    logging.info(f"Начало загрузки файла: {uploaded_file.name} ({file_size_mb:.2f} МБ)")
    
    # Проверяем, является ли файл большим (> 100 МБ)
    is_large_file = file_size_mb > 100
    
    if is_large_file and chunk_size is None:
        chunk_size = 100000  # По умолчанию 100 тыс. строк для больших файлов
        st.info(f"Файл большой ({file_size_mb:.2f} МБ). Загрузка будет выполнена частями.")

    try:
        if file_ext == '.csv':
            # Для больших CSV используем чанки
            if is_large_file and chunk_size:
                return _load_csv_in_chunks(uploaded_file, chunk_size)
            else:
                return _load_csv_standard(uploaded_file)
        elif file_ext in ('.xls', '.xlsx'):
            if is_large_file:
                st.warning("Большие Excel-файлы могут загружаться медленно. Рекомендуется использовать CSV.")
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file)
            logging.info(f"Успешно загружено {len(df)} строк из Excel, колонки: {list(df.columns)}")
            return df
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_ext}")
    except UnicodeDecodeError:
        raise ValueError("Сохраните ваш CSV-файл в кодировке UTF-8 и загрузите заново.")
    except pd.errors.EmptyDataError:
        logging.error("Пустой CSV-файл или нет данных.")
        raise ValueError("Файл пуст или не содержит данных.")
    except pd.errors.ParserError as e:
        logging.error(f"Ошибка парсинга: {str(e)}")
        raise ValueError(f"Ошибка чтения файла: {e}")
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        raise ValueError(f"Ошибка загрузки: {str(e)}")

def _load_csv_standard(uploaded_file) -> pd.DataFrame:
    """
    Стандартная загрузка CSV без разбиения на чанки.
    """
    data_bytes = uploaded_file.read()
    text_obj = StringIO(data_bytes.decode('utf-8', errors='replace'))
    try:
        df = pd.read_csv(text_obj, sep=None, engine='python', thousands=' ')
        if df.shape[1] == 1:
            logging.warning("Авто-детект нашёл только 1 столбец. Возможно необычный разделитель.")
        logging.info(f"Успешно прочитан CSV (auto-detect). Колонки: {list(df.columns)}")
        return df
    except Exception as e:
        logging.warning(f"Авто-определение разделителя не сработало: {e}")
        text_obj.seek(0)
        try:
            df_semicolon = pd.read_csv(text_obj, sep=';', encoding='utf-8', thousands=' ')
            if df_semicolon.shape[1] > 1:
                logging.info(f"Успешно прочитан CSV (sep=';'). Колонки: {list(df_semicolon.columns)}")
                return df_semicolon
        except:
            pass
        text_obj.seek(0)
        df_comma = pd.read_csv(text_obj, sep=',', encoding='utf-8', thousands=' ')
        if df_comma.shape[1] > 1:
            logging.info(f"Успешно прочитан CSV (sep=','). Колонки: {list(df_comma.columns)}")
            return df_comma
        raise ValueError("Не удалось автоматически определить разделитель CSV. Попробуйте ';' или ',' или сохраните файл в UTF-8.")

def _load_csv_in_chunks(uploaded_file, chunk_size: int) -> pd.DataFrame:
    """
    Загрузка большого CSV файла чанками для экономии памяти.
    """
    # Сначала определяем разделитель на маленьком образце
    sample_size = min(1024 * 10, uploaded_file.size)  # 10 КБ или меньше
    uploaded_file.seek(0)
    sample_data = uploaded_file.read(sample_size)
    sample_text = StringIO(sample_data.decode('utf-8', errors='replace'))
    
    # Пробуем разные разделители на образце
    separator = None
    encoding = 'utf-8'
    
    try:
        # Автоопределение разделителя
        pd.read_csv(sample_text, sep=None, engine='python', nrows=5)
        separator = None  # Авто-определение работает
    except:
        sample_text.seek(0)
        try:
            pd.read_csv(sample_text, sep=';', nrows=5)
            separator = ';'
        except:
            sample_text.seek(0)
            try:
                pd.read_csv(sample_text, sep=',', nrows=5)
                separator = ','
            except:
                raise ValueError("Не удалось определить разделитель CSV на основе образца.")
    
    # Теперь читаем весь файл чанками
    chunks = []
    uploaded_file.seek(0)
    
    for chunk in pd.read_csv(
        uploaded_file, 
        sep=separator, 
        engine='python' if separator is None else 'c',
        chunksize=chunk_size, 
        encoding=encoding, 
        errors='replace',
        thousands=' ',
        low_memory=True
    ):
        # Освобождаем память в процессе загрузки
        st.text(f"Загружено строк: {sum(len(df) for df in chunks) + len(chunk)}")
        chunks.append(chunk)
    
    # Объединяем все чанки
    df = pd.concat(chunks, ignore_index=True)
    logging.info(f"Успешно загружен большой CSV по частям. Всего строк: {len(df)}, колонки: {list(df.columns)}")
    
    return df

def convert_to_timeseries(df: pd.DataFrame, id_col: str, timestamp_col: str, target_col: str) -> pd.DataFrame:
    """
    Преобразует DataFrame в формат с колонками (item_id, timestamp, target).
    """
    df_local = df.copy()
    df_local.rename(columns={
        id_col: "item_id",
        timestamp_col: "timestamp",
        target_col: "target"
    }, inplace=True)
    df_local["item_id"] = df_local["item_id"].astype(str)
    df_local.sort_values(["item_id", "timestamp"], inplace=True)
    df_local.reset_index(drop=True, inplace=True)
    return df_local

def show_dataset_stats(df: pd.DataFrame):
    """
    Выводит статистику для числовых столбцов и количество пропусков.
    """
    st.write("**Основная статистика для числовых столбцов**:")
    try:
        st.write(df.describe(include=[float, int]))
    except ValueError:
        st.warning("Нет числовых столбцов для describe().")
    st.write("**Количество пропусков (NaN) по столбцам:**")
    missing_info = df.isnull().sum()
    st.write(missing_info)

def split_train_test(df: pd.DataFrame, 
                    date_col: str, 
                    test_size: float = 0.2, 
                    validation_size: float = 0.0) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Разделяет временной ряд на обучающую, тестовую и опционально валидационную выборки.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    date_col : str
        Название колонки с датами
    test_size : float
        Доля данных для тестовой выборки (0.0 - 1.0)
    validation_size : float
        Доля данных для валидационной выборки (0.0 - 1.0)
        
    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame]]
        Кортеж из train, test и опционально validation датафреймов
    """
    # Убеждаемся, что колонка даты в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
    
    # Сортируем по дате
    df_sorted = df.sort_values(date_col)
    
    # Вычисляем индексы разделения
    n = len(df_sorted)
    test_idx = int(n * (1 - test_size))
    
    if validation_size > 0:
        val_idx = int(n * (1 - test_size - validation_size))
        train = df_sorted.iloc[:val_idx]
        val = df_sorted.iloc[val_idx:test_idx]
        test = df_sorted.iloc[test_idx:]
        return train, test, val
    else:
        train = df_sorted.iloc[:test_idx]
        test = df_sorted.iloc[test_idx:]
        return train, test, None

def detect_outliers(df: pd.DataFrame, 
                   target_col: str, 
                   id_col: Optional[str] = None, 
                   method: str = 'iqr') -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Обнаруживает выбросы в целевой переменной.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Исходный датафрейм
    target_col : str
        Название целевой колонки
    id_col : str, optional
        Название колонки с идентификаторами
    method : str
        Метод обнаружения выбросов ('iqr' или 'zscore')
        
    Returns:
    --------
    Tuple[pd.DataFrame, pd.DataFrame]
        Датафрейм без выбросов и датафрейм только с выбросами
    """
    df_outliers = pd.DataFrame()
    df_clean = df.copy()
    
    if method == 'iqr':
        if id_col and id_col in df.columns:
            # Обрабатываем каждый ID отдельно
            for id_val in df[id_col].unique():
                mask = df[id_col] == id_val
                subset = df[mask]
                
                q1 = subset[target_col].quantile(0.25)
                q3 = subset[target_col].quantile(0.75)
                iqr = q3 - q1
                
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                outliers_mask = (subset[target_col] < lower_bound) | (subset[target_col] > upper_bound)
                df_outliers = pd.concat([df_outliers, subset[outliers_mask]])
                
                # Обновляем маску для очищенного датафрейма
                clean_indices = subset[~outliers_mask].index
                df_clean = df_clean.loc[df_clean.index.isin(clean_indices) | ~df_clean[id_col].isin([id_val])]
        else:
            # Обрабатываем весь датасет как один ряд
            q1 = df[target_col].quantile(0.25)
            q3 = df[target_col].quantile(0.75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers_mask = (df[target_col] < lower_bound) | (df[target_col] > upper_bound)
            df_outliers = df[outliers_mask]
            df_clean = df[~outliers_mask]
    
    elif method == 'zscore':
        if id_col and id_col in df.columns:
            # Обрабатываем каждый ID отдельно
            for id_val in df[id_col].unique():
                mask = df[id_col] == id_val
                subset = df[mask]
                
                z_scores = np.abs((subset[target_col] - subset[target_col].mean()) / subset[target_col].std())
                outliers_mask = z_scores > 3
                
                df_outliers = pd.concat([df_outliers, subset[outliers_mask]])
                
                # Обновляем маску для очищенного датафрейма
                clean_indices = subset[~outliers_mask].index
                df_clean = df_clean.loc[df_clean.index.isin(clean_indices) | ~df_clean[id_col].isin([id_val])]
        else:
            # Обрабатываем весь датасет как один ряд
            z_scores = np.abs((df[target_col] - df[target_col].mean()) / df[target_col].std())
            outliers_mask = z_scores > 3
            
            df_outliers = df[outliers_mask]
            df_clean = df[~outliers_mask]
    
    return df_clean, df_outliers
