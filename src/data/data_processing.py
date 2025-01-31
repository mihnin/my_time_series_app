import pandas as pd
import logging
import streamlit as st
from pathlib import Path
from io import StringIO

def load_data(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    """
    Загружает данные из CSV/Excel файла:
      - Если .csv, пытаемся автоматически определить разделитель (sep=None, engine='python').
      - Если не вышло, пробуем ';' и ','.
      - Если всё равно не вышло, выдаём ошибку про разделитель.
      - Если .xls/.xlsx, читаем через pd.read_excel.
      - Не парсим даты (парсим позже).
      - Если ошибка кодировки, просим сохранить в UTF-8.
      - Если прочитать не удалось, выдаём соответствующую ошибку.
    """
    if not uploaded_file:
        logging.error("Попытка загрузки без выбора файла")
        raise ValueError("Ошибка: Файл не выбран!")

    file_ext = Path(uploaded_file.name).suffix.lower()
    logging.info(f"Начало загрузки файла: {uploaded_file.name}")

    try:
        if file_ext == '.csv':
            # Пробуем автоматически определить разделитель
            data_bytes = uploaded_file.read()
            text_obj = StringIO(data_bytes.decode('utf-8', errors='replace'))

            try:
                # 1) Попытка auto-detect sep
                df = pd.read_csv(
                    text_obj,
                    sep=None,
                    engine='python',
                    thousands=' '  # Пробел как разделитель тысяч
                )
                if df.shape[1] == 1:
                    logging.warning("Авто-детект нашёл только 1 столбец. Возможно необычный разделитель.")
                logging.info(f"Успешно прочитан CSV (auto-detect). Колонки: {list(df.columns)}")
                return df
            except Exception as e:
                # 2) Фолбэк: пробуем сеп=';' и ','
                logging.warning(f"Авто-определение разделителя не сработало: {e}")

                # Пробуем ';'
                text_obj.seek(0)
                try:
                    df_semicolon = pd.read_csv(
                        text_obj,
                        sep=';',
                        encoding='utf-8',
                        thousands=' '
                    )
                    if df_semicolon.shape[1] > 1:
                        logging.info(f"Успешно прочитан CSV (sep=';'). Колонки: {list(df_semicolon.columns)}")
                        return df_semicolon
                except:
                    pass

                # Пробуем ','
                text_obj.seek(0)
                df_comma = pd.read_csv(
                    text_obj,
                    sep=',',
                    encoding='utf-8',
                    thousands=' '
                )
                if df_comma.shape[1] > 1:
                    logging.info(f"Успешно прочитан CSV (sep=','). Колонки: {list(df_comma.columns)}")
                    return df_comma

                # Если и это не помогло — кидаем ошибку
                raise ValueError("Не удалось автоматически определить разделитель CSV. "
                                 "Попробуйте ';' или ',' или сохраните файл в UTF-8.") from e

        elif file_ext in ('.xls', '.xlsx'):
            # Чтение Excel
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
    try:
        st.write(df.describe(include=[float, int]))
    except ValueError:
        st.warning("Нет числовых столбцов для describe().")

    st.write("**Количество пропусков (NaN) по столбцам:**")
    missing_info = df.isnull().sum()
    st.write(missing_info)

