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
<<<<<<< HEAD
    Стандартная загрузка CSV без разбиения на чанки, оптимизированная.
    """
    # Сбрасываем указатель на начало файла
    uploaded_file.seek(0)

    # Пробуем стандартные разделители с быстрым движком 'c'
    common_separators = [';', ',']
    for sep in common_separators:
        try:
            uploaded_file.seek(0) # Важно сбрасывать перед каждой попыткой
            df = pd.read_csv(uploaded_file, sep=sep, engine='c', low_memory=False)
            if df.shape[1] > 1:
                logging.info(f"Успешно прочитан CSV (sep='{sep}', engine='c'). Колонки: {list(df.columns)}")
                return df
        except Exception as e:
            logging.debug(f"Не удалось прочитать CSV с sep='{sep}' и engine='c': {e}")

    # Если стандартные разделители не сработали, пробуем авто-определение с engine='python'
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=None, engine='python', low_memory=False)
        logging.info(f"Успешно прочитан CSV (auto-detect, engine='python'). Колонки: {list(df.columns)}")
        if df.shape[1] == 1:
            logging.warning("Авто-детект нашёл только 1 столбец с engine='python'. Разделитель может быть необычным.")
        return df
    except Exception as e:
        logging.error(f"Полностью не удалось прочитать CSV: {e}")
=======
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
>>>>>>> 4283c45 (new)
        raise ValueError("Не удалось автоматически определить разделитель CSV. Попробуйте ';' или ',' или сохраните файл в UTF-8.")

def _load_csv_in_chunks(uploaded_file, chunk_size):
    """
    Оптимизированная загрузка большого CSV файла чанками для экономии памяти.
    """
    import concurrent.futures
    
    # Сначала определяем разделитель на маленьком образце
    sample_size = min(1024 * 10, uploaded_file.size)
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
    
    # Сбрасываем указатель на начало файла
    uploaded_file.seek(0)
    
    # Функция для обработки одного чанка
    def process_chunk(chunk):
        # Можно добавить дополнительную обработку чанка при необходимости
        return chunk
    
    # Читаем и обрабатываем чанки параллельно
    chunks = []
    
    # Используем ThreadPoolExecutor для параллельной обработки
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        
        # Читаем файл чанками
        for chunk in pd.read_csv(
            uploaded_file, 
            sep=separator, 
            engine='python' if separator is None else 'c',
            chunksize=chunk_size, 
            encoding=encoding, 
            errors='replace',
<<<<<<< HEAD
=======
            thousands=' ',
>>>>>>> 4283c45 (new)
            low_memory=True
        ):
            # Отправляем чанк на обработку
            futures.append(executor.submit(process_chunk, chunk))
            
        # Собираем обработанные чанки
        total_rows = 0
        for future in concurrent.futures.as_completed(futures):
            processed_chunk = future.result()
            total_rows += len(processed_chunk)
            chunks.append(processed_chunk)
            # Обновляем статус загрузки
            st.text(f"Загружено строк: {total_rows}")
    
    # Объединяем все чанки
    if not chunks:
        raise ValueError("Не удалось прочитать данные из файла")
    
    df = pd.concat(chunks, ignore_index=True)
    logging.info(f"Успешно загружен большой CSV по частям. Всего строк: {len(df)}, колонки: {list(df.columns)}")
    
    return df

def convert_to_timeseries(df: pd.DataFrame, id_col: str, timestamp_col: str, target_col: str) -> pd.DataFrame:
    """
    Преобразует DataFrame в формат с колонками (item_id, timestamp, target).
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Исходный датафрейм
    id_col : str
        Название колонки с идентификаторами
    timestamp_col : str
        Название колонки с датами
    target_col : str
        Название целевой колонки
        
    Returns:
    --------
    pd.DataFrame
        Датафрейм с переименованными колонками для AutoGluon
    """
    # Проверяем наличие необходимых колонок
    required_cols = [id_col, timestamp_col, target_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Отсутствуют необходимые колонки: {', '.join(missing_cols)}")
    
    # Создаем копию датафрейма, чтобы не изменять оригинал
    df_local = df.copy()
    
    # Переименовываем колонки
    column_mapping = {
        id_col: "item_id",
        timestamp_col: "timestamp",
        target_col: "target"
    }
    
    # Выполняем переименование с проверкой успешности
    df_local = df_local.rename(columns=column_mapping)
    
    # Проверяем, что колонки были успешно переименованы
    for new_col in ["item_id", "timestamp", "target"]:
        if new_col not in df_local.columns:
            raise ValueError(f"Не удалось создать колонку '{new_col}'. Проверьте правильность указанных имен колонок.")
    
    # Преобразуем item_id в строку и сортируем
    df_local["item_id"] = df_local["item_id"].astype(str)
    df_local = df_local.sort_values(["item_id", "timestamp"])
    df_local = df_local.reset_index(drop=True)
    
    # Логирование результата
    logging.info(f"Преобразовано в TimeSeriesDataFrame формат. Колонки: {list(df_local.columns)}")
    
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

def safe_convert_datetime(df, datetime_col, inplace=False):
    """
    Безопасно преобразует колонку в формат datetime с оптимизацией повторных вызовов.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Исходный датафрейм
    datetime_col : str
        Название колонки для преобразования
    inplace : bool, optional
        Выполнять ли преобразование в исходном датафрейме
        
    Returns:
    --------
    pandas.DataFrame
        Датафрейм с преобразованной колонкой
    """
    if datetime_col not in df.columns:
        raise ValueError(f"Колонка {datetime_col} не найдена в датафрейме")
    
    result_df = df if inplace else df.copy()
    
    # Проверяем, не является ли колонка уже datetime типом
    if not pd.api.types.is_datetime64_any_dtype(result_df[datetime_col]):
        result_df[datetime_col] = pd.to_datetime(result_df[datetime_col], errors="coerce")
        
    return result_df

def safely_prepare_timeseries_data(df, dt_col, id_col, tgt_col):
    """
    Безопасно подготавливает данные для TimeSeriesDataFrame с подробной диагностикой ошибок.
    
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
        
    Returns:
    --------
    pd.DataFrame
        Подготовленный датафрейм для TimeSeriesDataFrame
    """
    try:
        # Проверка наличия колонок
        required_cols = [dt_col, id_col, tgt_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise ValueError(f"Отсутствуют необходимые колонки: {', '.join(missing_cols)}")
        
        # Проверка типа данных в колонке с датой
        if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
            logging.info(f"Преобразование колонки {dt_col} в datetime")
            df = df.copy()
            df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
            
            # Проверяем результат преобразования
            if df[dt_col].isna().any():
                n_invalid = df[dt_col].isna().sum()
                logging.warning(f"После преобразования даты обнаружено {n_invalid} невалидных значений")
        
        # Проверяем и преобразуем id_col в строку, если нужно
        if not pd.api.types.is_object_dtype(df[id_col]) and not pd.api.types.is_string_dtype(df[id_col]):
            df = df.copy() if id(df) == id(df) else df
            df[id_col] = df[id_col].astype(str)
        
        # Преобразуем в формат для TimeSeriesDataFrame
        ts_df = convert_to_timeseries(df, id_col, dt_col, tgt_col)
        
        # Анализ результата
        logging.info(f"Успешно подготовлены данные. Строк: {len(ts_df)}, уникальных ID: {ts_df['item_id'].nunique()}")
        
        return ts_df
        
    except Exception as e:
        logging.error(f"Ошибка при подготовке данных: {str(e)}")
        if "timestamp" in str(e):
            logging.error(f"Проблема с колонкой timestamp. Проверьте правильность названия колонки даты: '{dt_col}'")
            logging.error(f"Доступные колонки в датафрейме: {list(df.columns)}")
        raise
