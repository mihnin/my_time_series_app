import pandas as pd
import logging
import streamlit as st
from typing import Union, Optional
from pathlib import Path
from feature_engineering import fill_missing_values

def load_data(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    """Загружает данные из CSV/Excel файла с валидацией и обработкой ошибок.
    
    Args:
        uploaded_file: Файл, загруженный через Streamlit file_uploader
    
    Returns:
        pd.DataFrame: Загруженные данные
        
    Raises:
        ValueError: При ошибках загрузки или неверном формате файла
    """
    if not uploaded_file:
        logging.error("Попытка загрузки без выбора файла")
        raise ValueError("Ошибка: Файл не выбран!")

    file_ext = Path(uploaded_file.name).suffix.lower()
    logging.info(f"Начало загрузки файла: {uploaded_file.name}")

    try:
        if file_ext == '.csv':
            with st.spinner("Чтение CSV файла..."):
                df = pd.read_csv(uploaded_file)
        elif file_ext in ('.xls', '.xlsx'):
            with st.spinner("Чтение Excel файла..."):
                df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_ext}")
                
        logging.info(f"Успешно загружено {len(df)} строк")
        return df

    except pd.errors.ParserError as e:
        logging.error(f"Ошибка парсинга: {str(e)}")
        raise ValueError(f"Ошибка чтения файла: {e}")
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        raise ValueError(f"Ошибка загрузки: {str(e)}")


def convert_to_timeseries(
    df: pd.DataFrame,
    id_col: str,
    timestamp_col: str,
    target_col: str,
    static_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """Преобразует DataFrame в формат временных рядов."""
    # ... (существующий код функции convert_to_timeseries)

# Удаляем/комментируем предыдущие дубли:
# def fill_missing_values(...):
#     ... (больше не нужно, используем из feature_engineering) ...
