import pandas as pd
import logging
import streamlit as st
from pathlib import Path

def load_data(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    """
    Загружает данные из CSV/Excel файла:
      - Для CSV используем sep=';'
      - Если при чтении CSV возникает ошибка кодировки, выдаём сообщение
        о необходимости сохранить файл в UTF-8.
      - Не парсим даты на этапе чтения, чтобы не требовать колонку 'Дата'.
        Парсинг делаем позже, когда пользователь выбрал dt_col.
    """
    if not uploaded_file:
        logging.error("Попытка загрузки без выбора файла")
        raise ValueError("Ошибка: Файл не выбран!")

    file_ext = Path(uploaded_file.name).suffix.lower()
    logging.info(f"Начало загрузки файла: {uploaded_file.name}")

    try:
        if file_ext == '.csv':
            df = pd.read_csv(
                uploaded_file,
                sep=';',
                encoding='utf-8',   # Может вызвать UnicodeDecodeError
                thousands=' '       # Пробел между тысячами (например: 30 060)
            )
        elif file_ext in ('.xls', '.xlsx'):
            # Чтение Excel
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_ext}")

        logging.info(f"Успешно загружено {len(df)} строк, колонки: {list(df.columns)}")
        return df

    except UnicodeDecodeError as e:
        # Специально обрабатываем ошибку кодировки
        raise ValueError("Сохраните ваш CSV-файл в кодировке UTF-8 и загрузите заново.")
    except pd.errors.ParserError as e:
        logging.error(f"Ошибка парсинга: {str(e)}")
        raise ValueError(f"Ошибка чтения файла: {e}")
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        raise ValueError(f"Ошибка загрузки: {str(e)}")


def convert_to_timeseries(df: pd.DataFrame, id_col: str, timestamp_col: str, target_col: str) -> pd.DataFrame:
    """
    Преобразует DataFrame в формат с колонками (item_id, timestamp, target).
    Переименовывает выбранные пользователем колонки в стандартные имена для TimeSeriesDataFrame.
    """
    df_local = df.copy()
    df_local.rename(columns={
        id_col: "item_id",
        timestamp_col: "timestamp",
        target_col: "target"
    }, inplace=True)

    # Приведение item_id к строке
    df_local["item_id"] = df_local["item_id"].astype(str)

    df_local.sort_values(["item_id", "timestamp"], inplace=True)
    df_local.reset_index(drop=True, inplace=True)
    return df_local


def show_dataset_stats(df: pd.DataFrame):
    """
    Выводит краткую статистику:
      - describe() для числовых столбцов
      - количество пропусков
    """
    st.write("**Основная статистика для числовых столбцов**:")
    st.write(df.describe(include=[float, int]))

    st.write("**Количество пропусков (NaN) по столбцам:**")
    missing_info = df.isnull().sum()
    st.write(missing_info)

