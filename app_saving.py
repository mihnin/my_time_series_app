import streamlit as st
import logging
import os
import json
from autogluon.timeseries import TimeSeriesPredictor
from src.config import get_config

# Используем константы из централизованной конфигурации вместо хардкода
MODEL_DIR = get_config("MODEL_DIR")
MODEL_INFO_FILE = get_config("MODEL_INFO_FILE")

def save_model_metadata(model_metadata=None, dt_col=None, tgt_col=None, id_col=None, static_feats=None, freq_val=None,
                        fill_method_val=None, group_cols_fill_val=None, use_holidays_val=None,
                        metric=None, presets=None, chosen_models=None, mean_only=False):
    """
    Сохраняет метаданные (колонки и настройки) в JSON-файл.
    
    Параметры:
    -----------
    model_metadata : dict, optional
        Словарь с метаданными модели. Если указан, значения будут взяты из него при отсутствии других параметров.
    dt_col : str, optional
        Имя колонки с датами.
    tgt_col : str, optional
        Имя целевой колонки.
    id_col : str, optional
        Имя колонки с идентификаторами.
    ... и другие параметры ...
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Инициализируем словарь метаданных
    info_dict = {}
    
    # Если предоставлены метаданные модели, используем их как основу
    if model_metadata is not None:
        # Копируем важные поля из model_metadata в наш словарь
        for key in ["dt_col", "tgt_col", "id_col", "freq", "horizon", "use_holidays", 
                    "static_features", "metric", "preset", "training_time"]:
            if key in model_metadata:
                info_dict[key] = model_metadata[key]
        
        # Копируем информацию о лучшей модели
        if "best_model" in model_metadata:
            info_dict["best_model"] = model_metadata["best_model"]
    
    # Перезаписываем значения явно указанными параметрами, если они предоставлены
    if dt_col is not None:
        info_dict["dt_col"] = dt_col
    if tgt_col is not None:
        info_dict["tgt_col"] = tgt_col
    if id_col is not None:
        info_dict["id_col"] = id_col
    if static_feats is not None:
        info_dict["static_feats"] = static_feats
    if freq_val is not None:
        info_dict["freq_val"] = freq_val
    if fill_method_val is not None:
        info_dict["fill_method_val"] = fill_method_val
    if group_cols_fill_val is not None:
        info_dict["group_cols_fill_val"] = group_cols_fill_val
    if use_holidays_val is not None:
        info_dict["use_holidays_val"] = use_holidays_val
    if metric is not None:
        info_dict["metric"] = metric
    if presets is not None:
        info_dict["presets"] = presets
    if chosen_models is not None:
        info_dict["chosen_models"] = chosen_models
    
    # mean_only всегда указан из-за значения по умолчанию
    info_dict["mean_only"] = mean_only
    
    path_json = os.path.join(MODEL_DIR, MODEL_INFO_FILE)
    try:
        with open(path_json, "w", encoding="utf-8") as f:
            json.dump(info_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении model_info.json: {e}")

def load_model_metadata():
    """
    Загружает метаданные из model_info.json.
    """
    path_json = os.path.join(MODEL_DIR, MODEL_INFO_FILE)
    if not os.path.exists(path_json):
        return None
    try:
        with open(path_json, "r", encoding="utf-8") as f:
            info = json.load(f)
        return info
    except Exception as e:
        logging.warning(f"Не удалось загрузить model_info.json: {e}")
        return None

def try_load_existing_model():
    """
    Если в папке MODEL_DIR есть ранее обученная модель (predictor.pkl),
    загружаем её и восстанавливаем настройки в session_state.
    """
    if not os.path.exists(MODEL_DIR):
        st.info("Папка с моделью не найдена — модель не загружена.")
        return

    predictor_path = os.path.join(MODEL_DIR, "predictor.pkl")
    if not os.path.exists(predictor_path):
        st.info("Файл predictor.pkl не найден — модель ещё не обучалась.")
        return

    try:
        loaded_predictor = TimeSeriesPredictor.load(MODEL_DIR)
        st.session_state["predictor"] = loaded_predictor
        st.info(f"Загружена ранее обученная модель из {MODEL_DIR}")

        meta = load_model_metadata()
        if meta:
            # Сначала сохраняем временные значения, которые будут применены при следующем рендеринге
            if "dt_col" in meta:
                st.session_state["_temp_dt_col"] = meta.get("dt_col", "<нет>")
            
            if "tgt_col" in meta:
                st.session_state["_temp_tgt_col"] = meta.get("tgt_col", "<нет>")
            
            if "id_col" in meta:
                st.session_state["_temp_id_col"] = meta.get("id_col", "<нет>")
            
            if "freq_val" in meta:
                # Преобразуем базовое значение частоты в полное описание для UI
                freq_base = meta.get("freq_val", "auto")
                from app_ui import FREQ_MAPPING
                freq_display = FREQ_MAPPING.get(freq_base, "auto (угадать)")
                st.session_state["_temp_freq"] = freq_display
            
            # Остальные поля можно устанавливать напрямую, т.к. они не связаны с виджетами в текущем рендеринге
            st.session_state["static_feats_key"] = meta.get("static_feats", [])
            st.session_state["fill_method_key"] = meta.get("fill_method_val", "None")
            st.session_state["group_cols_for_fill_key"] = meta.get("group_cols_fill_val", [])
            st.session_state["use_holidays_key"] = meta.get("use_holidays_val", False)
            st.session_state["metric_key"] = meta.get("metric", "MASE (Mean absolute scaled error)")
            st.session_state["presets_key"] = meta.get("presets", "medium_quality")
            st.session_state["models_key"] = meta.get("chosen_models", ["* (все)"])
            st.session_state["mean_only_key"] = meta.get("mean_only", False)
            
            # Сохраняем важные данные, которые могут потеряться при перезагрузке
            if "use_holidays_key" in st.session_state:
                st.session_state["_saved_use_holidays"] = st.session_state["use_holidays_key"]
                
            if "static_feats_key" in st.session_state:
                st.session_state["_saved_static_feats"] = st.session_state["static_feats_key"]
                
            if "page_choice" in st.session_state:
                st.session_state["_saved_page"] = st.session_state["page_choice"]
            
            st.info("Настройки из model_info.json восстановлены.")
            # Перезапускаем приложение с сохраненными данными
            st.rerun()
    
    except Exception as e:
        st.warning(f"Ошибка при загрузке модели: {e}")

