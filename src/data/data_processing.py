# src/data/data_processing.py
import pandas as pd
import logging
import streamlit as st
from pathlib import Path
from io import StringIO
import numpy as np
from typing import Optional, Tuple
from src.config.app_config import get_config

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

def _load_csv_in_chunks(uploaded_file, chunk_size):
    """
    Загрузка CSV в чанках для больших файлов.
    """
    # Сначала определяем разделитель
    uploaded_file.seek(0)
    sample_bytes = uploaded_file.read(10 * 1024)  # Читаем первые 10 КБ для определения разделителя
    sample_text = StringIO(sample_bytes.decode('utf-8', errors='replace'))
    
    # Пытаемся автоматически определить разделитель
    try:
        df_sample = pd.read_csv(sample_text, sep=None, engine='python', nrows=10)
        separator = ','  # По умолчанию запятая, если автоопределение работает
    except:
        # Если не получилось, пробуем разные разделители
        sample_text.seek(0)
        try:
            df_sample = pd.read_csv(sample_text, sep=';', nrows=10)
            separator = ';'
        except:
            separator = ','  # Если и это не сработало, используем запятую
    
    # Теперь читаем файл чанками с определенным разделителем
    uploaded_file.seek(0)
    chunks = []
    total_rows = 0
    
    # Создаем TextIOWrapper для чтения файла
    file_wrapper = StringIO(uploaded_file.read().decode('utf-8', errors='replace'))
    
    # Читаем чанки
    for chunk_df in pd.read_csv(file_wrapper, sep=separator, chunksize=chunk_size):
        processed_chunk = process_chunk(chunk_df)
        chunks.append(processed_chunk)
        total_rows += len(processed_chunk)
        logging.info(f"Загружено {total_rows} строк...")
    
    # Объединяем все чанки
    result_df = pd.concat(chunks, ignore_index=True)
    logging.info(f"Всего загружено {len(result_df)} строк из CSV.")
    return result_df

def process_chunk(chunk):
    # Можно добавить дополнительную обработку чанка при необходимости
    # Например, конвертацию типов, фильтрацию и т.д.
    return chunk

def safe_convert_datetime(df, datetime_col, inplace=False):
    """
    Безопасное конвертирование колонки в datetime.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм
    datetime_col : str
        Название колонки с датой/временем
    inplace : bool
        Изменять ли исходный датафрейм
        
    Returns:
    --------
    pd.DataFrame или None
        Преобразованный датафрейм (если inplace=False)
    """
    if not inplace:
        df = df.copy()
    
    if datetime_col not in df.columns:
        logging.warning(f"Колонка {datetime_col} не найдена в датафрейме")
        return df if not inplace else None
    
    # Получаем форматы дат из конфигурации, если доступна
    try:
        config = get_config()
        date_formats = config.get('auto_detection', {}).get('date_formats', [
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%d.%m.%Y %H:%M:%S"
        ])
    except:
        # Если конфигурация недоступна, используем стандартные форматы
        date_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%d.%m.%Y %H:%M:%S"]
    
    if pd.api.types.is_datetime64_dtype(df[datetime_col]):
        logging.info(f"Колонка {datetime_col} уже имеет тип datetime64")
        return df if not inplace else None
    
    # Пробуем разные форматы даты
    for date_format in date_formats:
        try:
            df[datetime_col] = pd.to_datetime(df[datetime_col], format=date_format, errors='raise')
            logging.info(f"Колонка {datetime_col} успешно преобразована в datetime с форматом {date_format}")
            return df if not inplace else None
        except ValueError:
            continue
    
    # Если конкретные форматы не подошли, пробуем автоопределение без dayfirst
    try:
        df[datetime_col] = pd.to_datetime(df[datetime_col], errors='coerce')
        # Проверяем, сколько строк стали NaT
        nat_count = df[datetime_col].isna().sum()
        if nat_count > 0:
            logging.warning(f"При конвертации {datetime_col} в datetime, {nat_count} значений стали NaT")
        return df if not inplace else None
    except Exception as e:
        logging.error(f"Ошибка при конвертации {datetime_col} в datetime: {e}")
        raise ValueError(f"Не удалось преобразовать колонку {datetime_col} в дату/время. Проверьте формат данных.")

def safely_prepare_timeseries_data(df, dt_col, id_col, tgt_col):
    """
    Безопасно подготавливает данные временного ряда, обрабатывая ошибки
    """
    try:
        # Проверяем наличие всех нужных колонок
        missing_cols = []
        if dt_col not in df.columns:
            missing_cols.append(f"колонка даты '{dt_col}'")
        if tgt_col not in df.columns:
            missing_cols.append(f"целевая колонка '{tgt_col}'")
        if id_col is not None and id_col not in df.columns:
            missing_cols.append(f"колонка ID '{id_col}'")
        
        if missing_cols:
            raise ValueError(f"В данных отсутствуют следующие колонки: {', '.join(missing_cols)}")
        
        # Копируем, чтобы не изменять исходный датафрейм
        df_copy = df.copy()
        
        # Конвертируем дату
        safe_convert_datetime(df_copy, dt_col, inplace=True)
        
        # Проверяем, что у нас нет пропусков в важных колонках
        if df_copy[dt_col].isna().any():
            logging.warning(f"В колонке даты {dt_col} обнаружены пропуски. Они будут удалены.")
            df_copy = df_copy.dropna(subset=[dt_col])
        
        if df_copy[tgt_col].isna().any():
            logging.warning(f"В целевой колонке {tgt_col} обнаружены пропуски. Они будут удалены.")
            df_copy = df_copy.dropna(subset=[tgt_col])
        
        if id_col is not None and df_copy[id_col].isna().any():
            logging.warning(f"В колонке ID {id_col} обнаружены пропуски. Они будут удалены.")
            df_copy = df_copy.dropna(subset=[id_col])
        
        # Проверяем, остались ли данные после удаления пропусков
        if len(df_copy) == 0:
            raise ValueError("После удаления строк с пропусками в данных не осталось записей.")
        
        if len(df_copy) < 10:
            logging.warning(f"После обработки в данных осталось мало записей: {len(df_copy)}. Это может привести к плохому качеству прогноза.")
        
        # Сортируем по дате
        df_copy = df_copy.sort_values(by=dt_col)
        
        return df_copy
    
    except Exception as e:
        logging.error(f"Ошибка при подготовке данных: {e}")
        raise

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
    Отображает основную статистику по датасету
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм для анализа
    """
    if df is None or len(df) == 0:
        st.warning("Датасет пуст или не загружен")
        return
    
    # Контейнер для метрик (показателей)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Строк", f"{len(df):,}".replace(",", " "))
    
    with col2:
        st.metric("📋 Колонок", f"{len(df.columns):,}".replace(",", " "))
    
    with col3:
        # Получаем объем памяти в МБ
        memory_usage = df.memory_usage(deep=True).sum() / (1024 * 1024)
        st.metric("💾 Размер в памяти", f"{memory_usage:.2f} МБ")
    
    with col4:
        # Процент пропусков
        missing_percent = df.isna().mean().mean() * 100
        st.metric("❓ Пропуски", f"{missing_percent:.2f}%")
    
    # Статистика по типам данных
    dtypes_count = df.dtypes.value_counts()
    dtypes_df = pd.DataFrame({
        'Тип данных': dtypes_count.index.astype(str),
        'Количество колонок': dtypes_count.values
    })
    
    # Статистика по пропускам в колонках
    missing_cols = df.isna().sum()
    missing_cols = missing_cols[missing_cols > 0]
    
    # Создаем две колонки: одна для типов данных, другая для пропусков
    dtype_col, missing_col = st.columns(2)
    
    with dtype_col:
        st.subheader("Типы данных")
        # Отображаем датафрейм с типами данных на всю ширину колонки
        st.dataframe(dtypes_df, use_container_width=True)
    
    with missing_col:
        st.subheader("Колонки с пропусками")
        if len(missing_cols) > 0:
            missing_df = pd.DataFrame({
                'Колонка': missing_cols.index,
                'Пропуски': missing_cols.values,
                'Процент': (missing_cols.values / len(df) * 100).round(2)
            }).sort_values('Пропуски', ascending=False)
            
            # Отображаем датафрейм с пропусками на всю ширину колонки
            st.dataframe(missing_df, use_container_width=True)
        else:
            st.info("В датасете нет пропусков")
    
    # Описательная статистика
    st.subheader("Описательная статистика")
    
    # Получаем описательную статистику и транспонируем для лучшего отображения
    desc_stats = df.describe(include='all').transpose().reset_index()
    desc_stats.rename(columns={'index': 'Колонка'}, inplace=True)
    
    # Округляем числовые колонки для лучшей читаемости
    for col in desc_stats.select_dtypes(include=['float']).columns:
        if col != 'Колонка':
            desc_stats[col] = desc_stats[col].round(3)
    
    # Отображаем описательную статистику на всю ширину экрана
    st.dataframe(desc_stats, use_container_width=True, height=400)

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
