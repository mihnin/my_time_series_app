import streamlit as st
import logging
import os
import json
from autogluon.timeseries import TimeSeriesPredictor
from src.config import get_config

# Используем константы из централизованной конфигурации вместо хардкода
MODEL_DIR = get_config("MODEL_DIR")
MODEL_INFO_FILE = get_config("MODEL_INFO_FILE")

def save_model_metadata(dt_col, tgt_col, id_col, static_feats, freq_val,
                        fill_method_val, group_cols_fill_val, use_holidays_val,
                        metric, presets, chosen_models, mean_only):
    """
    Сохраняет метаданные (колонки и настройки) в JSON-файл.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    info_dict = {
        "dt_col": dt_col,
        "tgt_col": tgt_col,
        "id_col": id_col,
        "static_feats": static_feats,
        "freq_val": freq_val,
        "fill_method_val": fill_method_val,
        "group_cols_fill_val": group_cols_fill_val,
        "use_holidays_val": use_holidays_val,
        "metric": metric,
        "presets": presets,
        "chosen_models": chosen_models,
        "mean_only": mean_only
    }
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
            st.session_state["dt_col_key"] = meta.get("dt_col", "<нет>")
            st.session_state["tgt_col_key"] = meta.get("tgt_col", "<нет>")
            st.session_state["id_col_key"]  = meta.get("id_col", "<нет>")
            st.session_state["static_feats_key"] = meta.get("static_feats", [])
            st.session_state["freq_key"] = meta.get("freq_val", "auto (угадать)")
            st.session_state["fill_method_key"] = meta.get("fill_method_val", "None")
            st.session_state["group_cols_for_fill_key"] = meta.get("group_cols_fill_val", [])
            st.session_state["use_holidays_key"] = meta.get("use_holidays_val", False)
            st.session_state["metric_key"] = meta.get("metric", "MASE (Mean absolute scaled error)")
            st.session_state["presets_key"] = meta.get("presets", "medium_quality")
            st.session_state["models_key"] = meta.get("chosen_models", ["* (все)"])
            st.session_state["mean_only_key"] = meta.get("mean_only", False)
            st.info("Настройки из model_info.json восстановлены.")
    except Exception as e:
        st.warning(f"Ошибка при загрузке модели: {e}")

