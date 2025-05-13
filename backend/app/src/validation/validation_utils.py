# src/validation/validation_utils.py
import pandas as pd
import logging

def validate_columns(df, required_columns, raise_error=True):
    """
    Проверяет наличие необходимых колонок в DataFrame.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм для проверки
    required_columns : list
        Список необходимых колонок
    raise_error : bool, optional
        Вызывать ли исключение или возвращать результат проверки
        
    Returns:
    --------
    bool or raises ValueError
        True, если все колонки найдены, иначе ValueError или False
    """
    if df is None:
        if raise_error:
            raise ValueError("DataFrame не инициализирован (None)")
        return False
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        if raise_error:
            raise ValueError(f"В DataFrame отсутствуют обязательные колонки: {', '.join(missing_columns)}")
        return False
    return True

def validate_session_state(keys, state_obj=None):
    """
    Проверяет наличие необходимых ключей в session_state.
    
    Parameters:
    -----------
    keys : list
        Список необходимых ключей
    state_obj : object, optional
        Объект состояния (по умолчанию st.session_state)
        
    Returns:
    --------
    bool
        True, если все ключи найдены и не None, иначе False
    """
    import streamlit as st
    state = state_obj if state_obj is not None else st.session_state
    
    missing_keys = []
    for key in keys:
        if key not in state or state[key] is None:
            missing_keys.append(key)
    
    if missing_keys:
        logging.warning(f"В session_state отсутствуют ключи: {', '.join(missing_keys)}")
        return False
    return True

def safe_get_from_dict(dictionary, key_path, default=None):
    """
    Безопасно извлекает значение из вложенного словаря по пути ключей.
    
    Parameters:
    -----------
    dictionary : dict
        Исходный словарь
    key_path : str or list
        Путь к ключу в виде строки с разделителями "." или списка ключей
    default : any, optional
        Значение по умолчанию, если ключ не найден
        
    Returns:
    --------
    any
        Значение по ключу или значение по умолчанию
    """
    if dictionary is None:
        return default
    
    if isinstance(key_path, str):
        key_path = key_path.split('.')
    
    current = dictionary
    for key in key_path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current