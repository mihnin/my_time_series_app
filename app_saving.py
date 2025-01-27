# app_saving.py
import streamlit as st
import pandas as pd
from openpyxl.styles import PatternFill
import yaml
import os
import json
import logging

MODEL_DIR = "AutogluonModels/TimeSeriesModel"
MODEL_INFO_FILE = "model_info.json"
CONFIG_PATH = "config/config.yaml"

from autogluon.timeseries import TimeSeriesPredictor

def format_fit_summary(fit_summary):
    """Форматирует fit_summary для более удобочитаемого вывода."""
    if not fit_summary:
        return "Fit Summary отсутствует."

    summary_str = "### Fit Summary:\n\n"
    if 'total_fit_time' in fit_summary:
        summary_str += f"- **Total Fit Time**: {fit_summary['total_fit_time']:.2f} seconds\n"
    if 'best_model' in fit_summary:
        summary_str += f"- **Best Model**: {fit_summary['best_model']}\n"
    if 'best_model_score' in fit_summary:
        summary_str += f"- **Best Model Score**: {fit_summary['best_model_score']:.4f}\n"

    if 'model_fit_summary' in fit_summary and fit_summary['model_fit_summary']:
        summary_str += "\n**Model Fit Details:**\n"
        for model_name, model_info in fit_summary['model_fit_summary'].items():
            summary_str += f"\n**Model: {model_name}**\n"
            if not isinstance(model_info, dict):
                summary_str += "  - Ошибка: отсутствуют детальные данные\n"
                continue

            # Стандартные ключи
            if 'fit_time' in model_info:
                summary_str += f"  - Fit Time: {model_info['fit_time']:.2f} seconds\n"
            if 'score' in model_info:
                summary_str += f"  - Score: {model_info['score']:.4f}\n"
            if 'eval_metric' in model_info:
                summary_str += f"  - Eval Metric: {model_info['eval_metric']}\n"
            if 'pred_count' in model_info:
                summary_str += f"  - Predictions Count: {model_info['pred_count']}\n"

            # Для ансамбля
            if 'child_model_names' in model_info:
                summary_str += f"  - Child Models: {model_info['child_model_names']}\n"
            if 'child_model_scores' in model_info:
                summary_str += f"  - Child Models' Scores: {model_info['child_model_scores']}\n"
            if 'child_model_weights' in model_info:
                summary_str += f"  - Child Models' Weights: {model_info['child_model_weights']}\n"

    return summary_str


def format_fit_summary_to_df(fit_summary):
    """Преобразует fit_summary в DataFrame для сохранения в Excel."""
    if not fit_summary or not isinstance(fit_summary, dict) or not fit_summary.get('model_fit_summary'):
        return pd.DataFrame({"Информация": ["Fit Summary отсутствует или не содержит данных о моделях"]})

    data = []
    if 'total_fit_time' in fit_summary:
        data.append({"Метрика": "Total Fit Time", "Значение": f"{fit_summary['total_fit_time']:.2f} seconds"})
    if 'best_model' in fit_summary:
        data.append({"Метрика": "Best Model", "Значение": fit_summary['best_model']})
    if 'best_model_score' in fit_summary:
        data.append({"Метрика": "Best Model Score", "Значение": f"{fit_summary['best_model_score']:.4f}"})

    if 'model_fit_summary' in fit_summary and fit_summary['model_fit_summary']:
        for model_name, model_info in fit_summary['model_fit_summary'].items():
            if isinstance(model_info, dict):
                data.append({"Метрика": f"Model: {model_name}", "Значение": "---"})
                if 'fit_time' in model_info:
                    data.append({"Метрика": f"  Fit Time ({model_name})", "Значение": f"{model_info['fit_time']:.2f} seconds"})
                if 'score' in model_info:
                    data.append({"Метрика": f"  Score ({model_name})", "Значение": f"{model_info['score']:.4f}"})
                if 'eval_metric' in model_info:
                    data.append({"Метрика": f"  Eval Metric ({model_name})", "Значение": model_info['eval_metric']})
                if 'pred_count' in model_info:
                    data.append({"Метрика": f"  Predictions Count ({model_name})", "Значение": model_info['pred_count']})
                if 'child_model_names' in model_info:
                    data.append({"Метрика": f"  Child Models ({model_name})", "Значение": str(model_info['child_model_names'])})
                if 'child_model_scores' in model_info:
                    data.append({"Метрика": f"  Child Models' Scores ({model_name})", "Значение": str(model_info['child_model_scores'])})
                if 'child_model_weights' in model_info:
                    data.append({"Метрика": f"  Child Models' Weights ({model_name})", "Значение": str(model_info['child_model_weights'])})
            else:
                logging.warning(f"Model fit summary for {model_name} is not a dictionary: {model_info}")

    return pd.DataFrame(data)


def load_config(path: str):
    """Загружает конфиг YAML (METRICS_DICT, AG_MODELS)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл конфигурации {path} не найден.")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    metrics_dict = data.get("metrics_dict", {})
    ag_models = data.get("ag_models", {})
    return metrics_dict, ag_models


def save_results_to_excel(save_path):
    """Функция для сохранения результатов в Excel."""
    try:
        df_train = st.session_state.get("df")
        lb = st.session_state.get("leaderboard")
        preds = st.session_state.get("predictions")
        stt_train = st.session_state.get("static_df_train")
        stt_fore  = st.session_state.get("static_df_fore")
        fit_summary_data = st.session_state.get("fit_summary")
        dt_col = st.session_state.get("dt_col_key")
        id_col = st.session_state.get("id_col_key")
        static_feats_val = st.session_state.get("static_feats_key", [])
        use_holidays_val = st.session_state.get("use_holidays_key", False)

        has_data_to_save = any([
            df_train is not None, lb is not None, preds is not None, 
            fit_summary_data,
            (stt_train is not None and not stt_train.empty if stt_train is not None else False),
            (stt_fore is not None and not stt_fore.empty if stt_fore is not None else False),
            (use_holidays_val and df_train is not None and 'russian_holiday' in df_train.columns)
        ])

        if not has_data_to_save:
            st.warning("Нет данных для сохранения в Excel. Сначала загрузите данные и обучите модель.")
            return False

        import openpyxl
        from openpyxl.utils import get_column_letter

        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            if preds is not None:
                pred_df_to_save = preds.reset_index()
                pred_df_to_save['timestamp'] = pd.to_datetime(pred_df_to_save['timestamp'])
                if static_feats_val and stt_train is not None:
                    pred_df_to_save = pd.merge(pred_df_to_save, stt_train, on='item_id', how='left')
                # Важно: здесь было pred_df_to_excel(...) - ЗАМЕНИЛИ на to_excel(...)
                pred_df_to_save.to_excel(writer, sheet_name="Predictions", index=False)
            elif df_train is not None:
                df_train.to_excel(writer, sheet_name="TrainData", index=False)

            if lb is not None:
                lb.to_excel(writer, sheet_name="Leaderboard", index=False)

            if fit_summary_data:
                fit_sum_df = format_fit_summary_to_df(fit_summary_data)
                fit_sum_df.to_excel(writer, sheet_name="FitSummaryDetails", index=False)

            if stt_train is not None and not stt_train.empty:
                stt_to_save = stt_train.copy()
                if use_holidays_val and 'russian_holiday' in df_train.columns:
                    first_timestamps = df_train.groupby(id_col)[dt_col].first().reset_index()
                    holiday_static = pd.merge(
                        stt_to_save[[id_col]],
                        df_train[[id_col, 'russian_holiday']],
                        left_on='item_id', right_on=id_col, how='left'
                    ).drop_duplicates(subset=[id_col])
                    stt_to_save = pd.merge(stt_to_save, holiday_static[[id_col, 'russian_holiday']], 
                                           on='item_id', how='left')
                stt_to_save.to_excel(writer, sheet_name="StaticTrainFeatures", index=False)

            if stt_fore is not None and not stt_fore.empty:
                stt_fore.to_excel(writer, sheet_name="StaticForeFeatures")

            if use_holidays_val and df_train is not None and 'russian_holiday' in df_train.columns:
                holiday_df = df_train[[dt_col, id_col, 'russian_holiday']].copy()
                holiday_df.to_excel(writer, sheet_name="RussianHolidays", index=False)

            # Подсветим лучшую модель
            if lb is not None and not lb.empty:
                workbook = writer.book
                sheet = writer.sheets["Leaderboard"]
                best_idx = lb.iloc[0].name
                best_model_name = lb.iloc[0]["model"]
                best_score = lb.iloc[0]["score_val"]

                fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                row_excel = best_idx + 2
                for col_idx in range(1, lb.shape[1] + 1):
                    cell = sheet.cell(row=row_excel, column=col_idx)
                    cell.fill = fill_green

                explanation_row = lb.shape[0] + 3
                explanation = (
                    f"Лучшая модель: {best_model_name}\n"
                    f"Причина: минимальный score_val = {best_score:.4f}"
                )
                sheet.cell(row=explanation_row, column=1).value = explanation

        st.success(f"Сохранено в {save_path}")
        return True

    except Exception as ex:
        st.error(f"Ошибка сохранения: {ex}")
        return False


def load_model_metadata():
    """Загружаем сохранённые настройки из model_info.json, если есть."""
    path_json = os.path.join(MODEL_DIR, MODEL_INFO_FILE)
    if not os.path.exists(path_json):
        return None
    try:
        with open(path_json, "r", encoding="utf-8") as f:
            info = json.load(f)
        return info
    except:
        return None


def save_model_metadata(dt_col, tgt_col, id_col, static_feats, freq_val,
                       fill_method_val, group_cols_fill_val, use_holidays_val,
                       metric, presets, chosen_models, mean_only):
    """Сохраняем все настройки (колонки, freq, метрику и т.д.) в JSON."""
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
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(info_dict, f, ensure_ascii=False, indent=2)


def try_load_existing_model():
    """Если в MODEL_DIR уже есть модель, то загружаем её и восстанавливаем настройки."""
    if not os.path.exists(MODEL_DIR):
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

            st.info("Настройки (колонки, freq, метрика и т.д.) восстановлены из model_info.json")
    except Exception as e:
        st.warning(f"Не удалось автоматически загрузить модель из {MODEL_DIR}. Ошибка: {e}")
