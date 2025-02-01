# src/data/data_processing.py
import pandas as pd
import logging
import streamlit as st
from pathlib import Path
from io import StringIO

def load_data(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    """
    Загружает данные из CSV/Excel файла.
    """
    if not uploaded_file:
        logging.error("Попытка загрузки без выбора файла")
        raise ValueError("Ошибка: Файл не выбран!")

    file_ext = Path(uploaded_file.name).suffix.lower()
    logging.info(f"Начало загрузки файла: {uploaded_file.name}")

    try:
        if file_ext == '.csv':
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
        elif file_ext in ('.xls', '.xlsx'):
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

