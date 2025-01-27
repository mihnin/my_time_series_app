# app.py
import streamlit as st
import plotly.express as px
import pandas as pd
import logging
import shutil
import yaml
import os
import json
import io
import zipfile

from autogluon.timeseries import TimeSeriesPredictor
from openpyxl.styles import PatternFill

# ВАЖНО: импортируем convert_to_timeseries один раз вверху
from src.data.data_processing import (
    load_data,
    convert_to_timeseries,
    show_dataset_stats
)
from src.features.feature_engineering import (
    fill_missing_values,
    add_russian_holiday_feature
)
from src.models.forecasting import (
    make_timeseries_dataframe,
    forecast
)
from src.utils.utils import (
    setup_logger,
    read_logs
)
from help_page import show_help_page  # <-- если ваш help_page.py в src/help_page.py, путь корректен

CONFIG_PATH = "config/config.yaml"
MODEL_DIR = "AutogluonModels/TimeSeriesModel"
MODEL_INFO_FILE = "model_info.json"


def load_config(path: str):
    """Загружает конфиг YAML (METRICS_DICT, AG_MODELS)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл конфигурации {path} не найден.")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    metrics_dict = data.get("metrics_dict", {})
    ag_models = data.get("ag_models", {})
    return metrics_dict, ag_models


METRICS_DICT, AG_MODELS = load_config(CONFIG_PATH)


def save_model_metadata(dt_col, tgt_col, id_col, static_feats, freq_val,
                       fill_method_val, group_cols_fill_val, use_holidays_val,
                       metric, presets, chosen_models, mean_only):
    """
    Сохраняем все настройки (колонки, freq, метрику и т.д.) в JSON,
    чтобы потом восстановить при обновлении страницы или повторном запуске.
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
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(info_dict, f, ensure_ascii=False, indent=2)


def load_model_metadata():
    """
    Загружаем сохранённые настройки (dt_col, freq, метрика и др.) из model_info.json, если есть.
    """
    path_json = os.path.join(MODEL_DIR, MODEL_INFO_FILE)
    if not os.path.exists(path_json):
        return None
    try:
        with open(path_json, "r", encoding="utf-8") as f:
            info = json.load(f)
        return info
    except:
        return None


def try_load_existing_model():
    """
    Если в папке MODEL_DIR уже есть обученная модель (TimeSeriesPredictor),
    то загружаем её и восстанавливаем все настройки (dt_col, freq и т.д.).
    """
    if not os.path.exists(MODEL_DIR):
        return
    try:
        loaded_predictor = TimeSeriesPredictor.load(MODEL_DIR)
        st.session_state["predictor"] = loaded_predictor
        st.info(f"Загружена ранее обученная модель из {MODEL_DIR}")

        meta = load_model_metadata()
        if meta:
            # Используем meta.get(..., default), чтобы не было KeyError при отсутствии ключа
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

def run_training():
    """Функция для запуска обучения модели."""
    df_train = st.session_state.get("df")
    if df_train is None:
        st.warning("Сначала загрузите Train!")
        return False

    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col  = st.session_state.get("id_col_key")

    if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
        st.error("Выберите корректно колонки: дата, target, ID!")
        return False

    try:
        shutil.rmtree("AutogluonModels", ignore_errors=True)

        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        fill_method_val = st.session_state.get("fill_method_key","None")
        group_cols_val = st.session_state.get("group_cols_for_fill_key",[])
        use_holidays_val = st.session_state.get("use_holidays_key", False)
        chosen_metric_val = st.session_state.get("metric_key")
        chosen_models_val = st.session_state.get("models_key")
        presets_val = st.session_state.get("presets_key", "medium_quality")
        mean_only_val = st.session_state.get("mean_only_key", False)
        p_length = st.session_state.get("prediction_length_key", 10)
        t_limit = st.session_state.get("time_limit_key", 60)

        df2 = df_train.copy()
        df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")

        if use_holidays_val:
            df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")

        df2 = fill_missing_values(df2, fill_method_val, group_cols_val)
        st.session_state["df"] = df2

        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df2[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col:"item_id"}, inplace=True)
            static_df = tmp

        df_ready = convert_to_timeseries(df2, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)

        actual_freq = None
        if freq_val != "auto (угадать)":
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
            actual_freq = freq_short

        hyperparams = None
        all_models_opt = "* (все)"
        if (len(chosen_models_val) == 1 and chosen_models_val[0] == all_models_opt) or len(chosen_models_val) == 0:
            hyperparams = None
        else:
            no_star = [m for m in chosen_models_val if m != all_models_opt]
            hyperparams = {m:{} for m in no_star}

        eval_key = chosen_metric_val.split(" ")[0]
        q_levels = [0.5] if mean_only_val else None

        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=p_length,
            eval_metric=eval_key,
            freq=actual_freq,
            quantile_levels=q_levels,
            path=MODEL_DIR
        )

        st.info("Начинаем обучение...")
        try:
            predictor.fit(
                train_data=ts_df,
                time_limit=t_limit,
                presets=presets_val,
                hyperparameters=hyperparams
            )
        except ValueError as e:
            # Если не смог угадать freq
            if "cannot be inferred" in str(e):
                st.error(
                    "Для параметра (freq) - укажите конкретное значение. "
                    "Система не смог определить частоту автоматически."
                )
                return False # Training failed
            else:
                raise

        st.session_state["predictor"] = predictor
        st.success("Модель успешно обучена!")

        lb = predictor.leaderboard(ts_df)
        st.session_state["leaderboard"] = lb
        st.subheader("Лидерборд (Leaderboard)")
        st.dataframe(lb)

        summ = predictor.fit_summary()
        st.session_state["fit_summary"] = summ

        if summ: # Check if summ is not None and not empty
            detailed_fit_summary_str = format_fit_summary(summ) # Форматируем Fit Summary
            with st.expander("Fit Summary (Подробно)"):
                st.markdown(detailed_fit_summary_str)
        else:
            st.warning("Fit Summary is empty. Check training logs for potential issues.") # Inform user if empty
            with st.expander("Fit Summary (Подробно)"): # Still show expander, but with message
                st.text("Fit Summary is not available.")


        if not lb.empty:
            best_model = lb.iloc[0]["model"]
            best_score = lb.iloc[0]["score_val"]
            # Сохраняем название и score лучшей модели
            st.session_state["best_model_name"] = best_model
            st.session_state["best_model_score"] = best_score
            st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")


        # Сохраняем все настройки в JSON
        save_model_metadata(
            dt_col, tgt_col, id_col,
            static_feats_val, freq_val,
            fill_method_val, group_cols_val,
            use_holidays_val, chosen_metric_val,
            presets_val, chosen_models_val, mean_only_val
        )
        return True # Training successful

    except Exception as ex:
        st.error(f"Ошибка обучения: {ex}")
        return False # Training failed

def format_fit_summary(fit_summary): # Keep existing formatting function - for display
    """Форматирует fit_summary для более удобочитаемого вывода в Streamlit."""
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
            if 'fit_time' in model_info:
                summary_str += f"  - Fit Time: {model_info['fit_time']:.2f} seconds\n"
            if 'score' in model_info:
                summary_str += f"  - Score: {model_info['score']:.4f}\n"
            if 'eval_metric' in model_info:
                summary_str += f"  - Eval Metric: {model_info['eval_metric']}\n"
            if 'pred_count' in model_info:
                summary_str += f"  - Predictions Count: {model_info['pred_count']}\n"
            # Добавьте другие детали из model_info, которые важны

    return summary_str

def format_fit_summary_to_df(fit_summary): # New function to format to DataFrame for Excel
    """Преобразует fit_summary в DataFrame для сохранения в Excel."""
    if not fit_summary:
        return pd.DataFrame({"Информация": ["Fit Summary отсутствует"]}) # Return DataFrame even if empty

    data = []
    if 'total_fit_time' in fit_summary:
        data.append({"Метрика": "Total Fit Time", "Значение": f"{fit_summary['total_fit_time']:.2f} seconds"})
    if 'best_model' in fit_summary:
        data.append({"Метрика": "Best Model", "Значение": fit_summary['best_model']})
    if 'best_model_score' in fit_summary:
        data.append({"Метрика": "Best Model Score", "Значение": f"{fit_summary['best_model_score']:.4f}"})

    if 'model_fit_summary' in fit_summary and fit_summary['model_fit_summary']:
        for model_name, model_info in fit_summary['model_fit_summary'].items():
            data.append({"Метрика": f"Model: {model_name}", "Значение": "---"}) # Separator
            if 'fit_time' in model_info:
                data.append({"Метрика": f"  Fit Time ({model_name})", "Значение": f"{model_info['fit_time']:.2f} seconds"})
            if 'score' in model_info:
                data.append({"Метрика": f"  Score ({model_name})", "Значение": f"{model_info['score']:.4f}"})
            if 'eval_metric' in model_info:
                data.append({"Метрика": f"  Eval Metric ({model_name})", "Значение": model_info['eval_metric']})
            if 'pred_count' in model_info:
                data.append({"Метрика": f"  Predictions Count ({model_name})", "Значение": model_info['pred_count']})
            # Добавьте другие детали из model_info, которые важны

    return pd.DataFrame(data)


def run_prediction():
    """Функция для запуска прогнозирования."""
    predictor = st.session_state.get("predictor")
    if predictor is None:
        st.warning("Сначала обучите модель или загрузите уже существующую!")
        return False

    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col  = st.session_state.get("id_col_key")

    if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
        st.error("Проверьте, что выбраны колонки: дата, target, ID!")
        return False

    df_train = st.session_state.get("df") # Always use df_train for prediction

    if df_train is None: # Only check for train data
        st.error("Нет train данных!") # Update error message
        return False

    try:
        st.subheader("Прогноз на TRAIN") # Update subheader, always predict on train
        df_pred = df_train.copy() # Prediction is always on train data

        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")

        if st.session_state.get("use_holidays_key", False):
            df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")

        df_pred = fill_missing_values(
            df_pred,
            st.session_state.get("fill_method_key","None"),
            st.session_state.get("group_cols_for_fill_key",[])
        )


        st.session_state["df"] = df_pred # Update df in session state

        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df_pred[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col:"item_id"}, inplace=True)
            static_df = tmp

        if tgt_col not in df_pred.columns:
            df_pred[tgt_col] = None

        df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_prepared, static_df=static_df)

        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        if freq_val != "auto (угадать)":
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")

        preds = forecast(predictor, ts_df)
        st.session_state["predictions"] = preds

        st.subheader("Предсказанные значения (первые строки)")
        st.dataframe(preds.reset_index().head())

        # Повторно выводим лучшую модель (с обучения)
        best_name = st.session_state.get("best_model_name", None)
        best_score = st.session_state.get("best_model_score", None)
        if best_name is not None:
            st.info(f"Лучшая модель при обучении была: {best_name}, score_val={best_score:.4f}")

        # Графики
        if "0.5" in preds.columns:
            preds_df = preds.reset_index().rename(columns={"0.5": "prediction"})
            unique_ids = preds_df["item_id"].unique()
            st.subheader("Графики прогноза (0.5) (первые)")
            max_graphs = 3
            for i, uid in enumerate(unique_ids[:max_graphs]):
                subset = preds_df[preds_df["item_id"] == uid]
                fig_ = px.line(
                    subset, x="timestamp", y="prediction",
                    title=f"Прогноз для item_id={uid} (0.5)",
                    markers=True
                )
                st.plotly_chart(fig_, use_container_width=True)
        else:
            st.info("Нет колонки '0.5' — возможно mean_only=False или отключены квантили.")
        return True # Prediction successful

    except Exception as ex:
        st.error(f"Ошибка прогноза: {ex}")
        return False # Prediction failed

def save_results_to_excel(save_path):
    """Функция для сохранения результатов в Excel."""
    try:
        df_train = st.session_state.get("df")
        lb = st.session_state.get("leaderboard")
        preds = st.session_state.get("predictions")
        stt_train = st.session_state.get("static_df_train")
        stt_fore  = st.session_state.get("static_df_fore")
        fit_summary_data = st.session_state.get("fit_summary")


        import openpyxl
        from openpyxl.utils import get_column_letter

        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            if preds is not None: # If predictions exist, save them as "Predictions"
                preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False) # Renamed sheet to "Predictions"
            elif df_train is not None: # If no predictions but train data, save train data
                df_train.to_excel(writer, sheet_name="TrainData", index=False) # Save train data if no predictions

            if lb is not None:
                lb.to_excel(writer, sheet_name="Leaderboard", index=False)
            if fit_summary_data: # Save fit summary to a separate sheet
                fit_sum_df = format_fit_summary_to_df(fit_summary_data) # Convert summary to DataFrame
                fit_sum_df.to_excel(writer, sheet_name="FitSummaryDetails", index=False) # Save to "FitSummaryDetails"
            if stt_train is not None and not stt_train.empty:
                stt_train.to_excel(writer, sheet_name="StaticTrainFeatures")
            if stt_fore is not None and not stt_fore.empty:
                stt_fore.to_excel(writer, sheet_name="StaticForeFeatures")

            # Подсветим лучшую модель
            if lb is not None and not lb.empty:
                workbook = writer.book
                sheet = writer.sheets["Leaderboard"]
                # Предположим, что лучшая модель - первая строка Leaderboard (строка 0)
                best_idx = lb.iloc[0].name
                best_model_name = lb.iloc[0]["model"]
                best_score = lb.iloc[0]["score_val"]

                fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                row_excel = best_idx + 2  # +2 потому что в Excel первая строка - заголовки
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
        return True # Save successful
    except Exception as ex:
        st.error(f"Ошибка сохранения: {ex}")
        return False # Save failed


def main():
    setup_logger()
    logging.info("=== Запуск приложения Streamlit (main) ===")

    # Пытаемся загрузить модель, если она уже есть
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try_load_existing_model()

    pages = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", pages, key="page_choice")

    if choice == "Help":
        show_help_page()
        return

    st.title("AutoGluon Приложение: Прогнозирование временных рядов")

    # Инициализация session_state ключей, если их нет
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "df_forecast" in st.session_state: # Remove df_forecast from session state
        del st.session_state["df_forecast"]
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None
    if "static_df_train" not in st.session_state:
        st.session_state["static_df_train"] = None
    if "static_df_fore" in st.session_state: # Remove static_df_fore from session state
        del st.session_state["static_df_fore"]

    # Храним лучшую модель и её score, чтобы показать и при прогнозе
    if "best_model_name" not in st.session_state:
        st.session_state["best_model_name"] = None
    if "best_model_score" not in st.session_state:
        st.session_state["best_model_score"] = None

    # ========== 1) Загрузка ==========
    st.sidebar.header("1. Загрузка данных")
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv","xls","xlsx"], key="train_file_uploader")
    # forecast_file = st.sidebar.file_uploader("Forecast (необязательно)", type=["csv","xls","xlsx"], key="forecast_file_uploader") # REMOVE forecast_file_uploader

    if st.sidebar.button("Загрузить данные", key="load_data_btn"):
        if not train_file:
            st.error("Train-файл обязателен!")
        else:
            try:
                df_train = load_data(train_file)
                st.session_state["df"] = df_train
                st.success("Train-файл загружен!")
                st.dataframe(df_train.head())

                st.subheader("Статистика Train")
                show_dataset_stats(df_train)

                # if forecast_file: # REMOVE forecast_file block
                #     df_fore = load_data(forecast_file)
                #     st.session_state["df_forecast"] = df_fore
                #     st.success("Forecast-файл загружен!")
                #     st.dataframe(df_fore.head())
                # else:
                st.session_state["df_forecast"] = None # Ensure df_forecast is None
                st.info("Функционал Forecast файла отключен.") # Inform user forecast is disabled
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")

    # ========== 2) Настройка колонок ==========
    st.sidebar.header("2. Колонки датасета")
    df_current = st.session_state["df"]
    if df_current is not None:
        all_cols = list(df_current.columns)
    else:
        all_cols = []

    # Проверяем, если сохранённые колонки не подходят, сбрасываем
    dt_stored = st.session_state.get("dt_col_key", "<нет>")
    if dt_stored not in ["<нет>"] + all_cols:
        st.session_state["dt_col_key"] = "<нет>"

    tgt_stored = st.session_state.get("tgt_col_key", "<нет>")
    if tgt_stored not in ["<нет>"] + all_cols:
        st.session_state["tgt_col_key"] = "<нет>"

    id_stored = st.session_state.get("id_col_key", "<нет>")
    if id_stored not in ["<нет>"] + all_cols:
        st.session_state["id_col_key"] = "<нет>"

    static_feats_stored = st.session_state.get("static_feats_key", [])
    valid_static_feats = [col for col in static_feats_stored if col in all_cols]
    st.session_state["static_feats_key"] = valid_static_feats

    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"] + all_cols, key="dt_col_key")
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"] + all_cols, key="tgt_col_key")
    id_col  = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"] + all_cols, key="id_col_key")

    st.sidebar.header("Статические признаки (до 3)")
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    static_feats = st.sidebar.multiselect(
        "Статические колонки:",
        possible_static,
        default=st.session_state["static_feats_key"],
        key="static_feats_key"
    )

    use_holidays = st.sidebar.checkbox(
        "Учитывать праздники РФ?",
        value=st.session_state.get("use_holidays_key", False),
        key="use_holidays_key"
    )

    # ========== 3) Пропуски ==========
    st.sidebar.header("3. Обработка пропусков")
    fill_options = ["None", "Constant=0", "Group mean", "Forward fill"]
    fill_method = st.sidebar.selectbox("Способ заполнения пропусков", fill_options, key="fill_method_key")
    group_cols_for_fill = []
    if fill_method in ["Group mean", "Forward fill"]:
        group_cols_for_fill = st.sidebar.multiselect(
            "Колонки для группировки",
            static_feats,
            key="group_cols_for_fill_key"
        )

    # ========== 4) Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    freq_options = ["auto (угадать)", "D (день)", "H (час)", "M (месяц)", "B (рабочие дни)"]
    chosen_freq = st.sidebar.selectbox("freq", freq_options, index=0, key="freq_key")

    # ========== 5) Метрика и модели ==========
    st.sidebar.header("5. Метрика и модели")
    metrics_list = list(METRICS_DICT.keys())
    if st.session_state.get("metric_key", None) not in metrics_list:
        st.session_state["metric_key"] = metrics_list[0]

    chosen_metric = st.sidebar.selectbox(
        "Метрика", metrics_list,
        index=metrics_list.index(st.session_state["metric_key"]),
        key="metric_key"
    )

    all_models_opt = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_opt] + model_keys
    chosen_models = st.sidebar.multiselect(
        "Модели AutoGluon",
        model_choices,
        default=st.session_state.get("models_key", [all_models_opt]),
        key="models_key"
    )

    presets_list = ["fast_training","medium_quality","high_quality","best_quality"]
    if st.session_state.get("presets_key", None) not in presets_list:
        st.session_state["presets_key"] = "medium_quality"

    presets = st.sidebar.selectbox("Presets", presets_list,
                                   index=presets_list.index(st.session_state["presets_key"]),
                                   key="presets_key")

    prediction_length = st.sidebar.number_input("prediction_length", 1, 365, 10, key="prediction_length_key")
    time_limit = st.sidebar.number_input("time_limit (sec)", 10, 36000, 60, key="time_limit_key")
    mean_only = st.sidebar.checkbox("Прогнозировать только среднее (mean)?",
                                    value=st.session_state.get("mean_only_key", False),
                                    key="mean_only_key")

    # Предварительный график
    if df_current is not None and dt_col != "<нет>" and tgt_col != "<нет>":
        try:
            df_plot = df_current.copy()
            df_plot[dt_col] = pd.to_datetime(df_plot[dt_col], errors="coerce")
            df_plot = df_plot.dropna(subset=[dt_col])

            if id_col != "<нет>":
                fig_target = px.line(
                    df_plot.sort_values(dt_col),
                    x=dt_col, y=tgt_col,
                    color=id_col,
                    title="График Target по ID"
                )
            else:
                fig_target = px.line(
                    df_plot.sort_values(dt_col),
                    x=dt_col, y=tgt_col,
                    title="График Target (без ID)"
                )
            st.subheader("Предварительный анализ Target")
            st.plotly_chart(fig_target, use_container_width=True)
        except Exception as e:
            st.warning(f"Не удалось построить график: {e}")

    # ========== 6) Обучение модели ==========
    st.sidebar.header("6. Обучение модели")
    train_and_predict_automatically = st.sidebar.checkbox("Обучение, Прогноз и Сохранение", key="train_predict_save_checkbox")

    if st.sidebar.button("Обучить модель", key="fit_model_btn"): # Only keep "Обучить модель" button
        train_success = run_training() # Run training
        if train_success and train_and_predict_automatically: # Check checkbox AND training success
            predict_success = run_prediction() # Run prediction if checkbox is checked and training was successful
            if predict_success:
                save_path_val = st.session_state.get("save_path_key", "results.xlsx")
                save_result = save_results_to_excel(save_path_val) # Save results
                if save_result:
                    st.info("Обучение, прогноз и сохранение результатов выполнены успешно!")


    # ========== 7) Прогноз ==========
    st.sidebar.header("7. Прогноз")
    if st.sidebar.button("Сделать прогноз", key="predict_btn"):
        run_prediction()

    # ========== 8) Сохранение результатов (Excel) ==========
    st.sidebar.header("8. Сохранение результатов прогноза")
    save_path = st.sidebar.text_input("Excel-файл", "results.xlsx", key="save_path_key")
    if st.sidebar.button("Сохранить результаты", key="save_btn"):
        save_results_to_excel(save_path)

    # ========== 9) Логи приложения ==========
    st.sidebar.header("9. Логи приложения")
    if st.sidebar.button("Показать логи", key="show_logs_btn"):
        logs_ = read_logs()
        st.subheader("Логи")
        st.text(logs_)

    if st.sidebar.button("Скачать логи", key="download_logs_btn"):
        log_data = read_logs()
        if log_data:
            st.download_button(
                label="Скачать логи",
                data=log_data,
                file_name="app.log",
                mime="text/plain"
            )
        else:
            st.warning("Лог-файл пуст или не найден.")


    # ========== 10) Выгрузка моделей и логов ==========
    st.sidebar.header("10. Выгрузка моделей и логов")
    if st.sidebar.button("Скачать все содержимое AutogluonModels", key="download_model_and_logs"):
        if not os.path.exists("AutogluonModels"):
            st.error("Папка 'AutogluonModels' не найдена. Сначала обучите модель.")
        else:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk("AutogluonModels"):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start="AutogluonModels")
                        zipf.write(file_path, arcname=arcname)

            zip_buf.seek(0)
            st.download_button(
                label="Скачать архив (модели и логи)",
                data=zip_buf,
                file_name="AutogluonModels.zip",
                mime="application/zip"
            )
            st.info("Содержимое папки AutogluonModels заархивировано.")


if __name__ == "__main__":
    main()