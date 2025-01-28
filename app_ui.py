# app_ui.py
import streamlit as st
import yaml
import os
import pandas as pd
import plotly.express as px

from src.data.data_processing import load_data, show_dataset_stats

CONFIG_PATH = "config/config.yaml"

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
metrics_list = list(METRICS_DICT.keys())
presets_list = ["fast_training", "medium_quality", "high_quality", "best_quality"]
all_models_opt = "* (все)"
model_keys = list(AG_MODELS.keys())
model_choices = [all_models_opt] + model_keys


def setup_ui():
    # Пишем версию в «верхнем левом углу» (просто выводим перед заголовком):
    st.markdown("### Версия 1.0")

    # Меняем название
    st.title("Бизнес-приложение для прогнозирования временных рядов")

    pages = ["Главная", "Help"]
    page_choice = st.sidebar.selectbox("Навигация", pages, key="page_choice")

    # Инициализация session_state ключей:
    session_keys = [
        "df", "predictor", "leaderboard", "predictions", "fit_summary",
        "static_df_train", "static_df_fore", "best_model_name", "best_model_score",
        "df_forecast", "metric_key", "presets_key", "models_key"
    ]
    for key in session_keys:
        if key not in st.session_state:
            if key == "metric_key":
                st.session_state[key] = metrics_list[0]
            elif key == "presets_key":
                st.session_state[key] = "medium_quality"
            elif key == "models_key":
                st.session_state[key] = [all_models_opt]
            else:
                st.session_state[key] = None

    # Удаляем df_forecast и static_df_fore (если не используется):
    if "df_forecast" in st.session_state:
        del st.session_state["df_forecast"]
    if "static_df_fore" in st.session_state:
        del st.session_state["static_df_fore"]

    # ========== (1) Загрузка ==========
    st.sidebar.header("1. Загрузка данных")
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv","xls","xlsx"], key="train_file_uploader")

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
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")

    # ========== (2) Настройка колонок ==========
    st.sidebar.header("2. Колонки датасета")
    df_current = st.session_state["df"]
    all_cols = list(df_current.columns) if df_current is not None else []

    if "dt_col_key" not in st.session_state:
        st.session_state["dt_col_key"] = "<нет>"
    if "tgt_col_key" not in st.session_state:
        st.session_state["tgt_col_key"] = "<нет>"
    if "id_col_key" not in st.session_state:
        st.session_state["id_col_key"] = "<нет>"

    dt_stored = st.session_state["dt_col_key"]
    tgt_stored = st.session_state["tgt_col_key"]
    id_stored  = st.session_state["id_col_key"]

    # Если ранее сохранённые имена колонок вдруг не существуют — сбрасываем их
    if dt_stored not in ["<нет>"] + all_cols:
        st.session_state["dt_col_key"] = "<нет>"
    if tgt_stored not in ["<нет>"] + all_cols:
        st.session_state["tgt_col_key"] = "<нет>"
    if id_stored not in ["<нет>"] + all_cols:
        st.session_state["id_col_key"] = "<нет>"

    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"] + all_cols, key="dt_col_key")
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"] + all_cols, key="tgt_col_key")
    id_col  = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"] + all_cols, key="id_col_key")

    st.sidebar.header("Статические признаки (до 3)")
    if "static_feats_key" not in st.session_state:
        st.session_state["static_feats_key"] = []

    # Фильтрация: убираем из session_state["static_feats_key"] те признаки,
    # которых больше нет в текущем датасете:
    existing_static_feats = st.session_state["static_feats_key"]
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    filtered_feats = [feat for feat in existing_static_feats if feat in possible_static]
    if len(filtered_feats) != len(existing_static_feats):
        st.session_state["static_feats_key"] = filtered_feats

    # multiselect для статических признаков
    static_feats = st.sidebar.multiselect(
        "Статические колонки:",
        possible_static,
        key="static_feats_key"
    )

    if "use_holidays_key" not in st.session_state:
        st.session_state["use_holidays_key"] = False
    st.sidebar.checkbox("Учитывать праздники РФ?",
                        value=st.session_state["use_holidays_key"],
                        key="use_holidays_key")

    # ========== (3) Пропуски ==========
    st.sidebar.header("3. Обработка пропусков")
    fill_options = ["None", "Constant=0", "Group mean", "Forward fill"]
    if "fill_method_key" not in st.session_state:
        st.session_state["fill_method_key"] = "None"
    st.sidebar.selectbox("Способ заполнения пропусков", fill_options, key="fill_method_key")

    if "group_cols_for_fill_key" not in st.session_state:
        st.session_state["group_cols_for_fill_key"] = []
    st.sidebar.multiselect("Колонки для группировки",
                           static_feats,
                           key="group_cols_for_fill_key")

    # ========== (4) Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    freq_options = ["auto (угадать)", "D (день)", "H (час)", "M (месяц)", "B (рабочие дни)"]
    if "freq_key" not in st.session_state:
        st.session_state["freq_key"] = "auto (угадать)"
    st.sidebar.selectbox("freq", freq_options, index=0, key="freq_key")

    # ========== (5) Метрика и модели ==========
    st.sidebar.header("5. Метрика и модели")
    st.sidebar.selectbox(
        "Метрика",
        metrics_list,
        index=metrics_list.index(st.session_state["metric_key"]),
        key="metric_key"
    )

    st.sidebar.multiselect("Модели AutoGluon", model_choices, key="models_key")

    st.sidebar.selectbox(
        "Presets",
        presets_list,
        index=presets_list.index(st.session_state["presets_key"]),
        key="presets_key"
    )

    st.sidebar.number_input("prediction_length", 1, 365, 10, key="prediction_length_key")
    st.sidebar.number_input("time_limit (sec)", 10, 36000, 60, key="time_limit_key")
    st.sidebar.checkbox("Прогнозировать только среднее (mean)?",
                        value=st.session_state.get("mean_only_key", False),
                        key="mean_only_key")

    # Предварительный график (с парсингом даты после выбора dt_col)
    if df_current is not None and dt_col != "<нет>" and tgt_col != "<нет>":
        try:
            df_plot = df_current.copy()
            # Преобразуем выбранную колонку в datetime (dayfirst=True, если нужно)
            df_plot[dt_col] = pd.to_datetime(df_plot[dt_col], errors="coerce", dayfirst=True)
            df_plot = df_plot.dropna(subset=[dt_col])

            if id_col != "<нет>":
                fig_target = px.line(
                    df_plot.sort_values(dt_col),
                    x=dt_col,
                    y=tgt_col,
                    color=id_col,
                    title="График Target по ID"
                )
            else:
                fig_target = px.line(
                    df_plot.sort_values(dt_col),
                    x=dt_col,
                    y=tgt_col,
                    title="График Target (без ID)"
                )
            st.subheader("Предварительный анализ Target")
            st.plotly_chart(fig_target, use_container_width=True)
        except Exception as e:
            st.warning(f"Не удалось построить график: {e}")

    # ========== (6) Обучение модели ==========
    st.sidebar.header("6. Обучение модели")
    st.sidebar.checkbox("Обучение, Прогноз и Сохранение", key="train_predict_save_checkbox")
    st.sidebar.button("Обучить модель", key="fit_model_btn")

    # ========== (7) Прогноз ==========
    st.sidebar.header("7. Прогноз")
    st.sidebar.button("Сделать прогноз", key="predict_btn")

    # ========== (8) Сохранение результатов ==========
    st.sidebar.header("8. Сохранение результатов прогноза")
    st.sidebar.text_input("Файл для сохранения результатов (CSV/XLSX)", "results.xlsx", key="save_path_key")
    st.sidebar.button("Сохранить результаты", key="save_btn")

    # ========== (9) Логи приложения ==========
    st.sidebar.header("9. Логи приложения")
    st.sidebar.button("Показать логи", key="show_logs_btn")
    st.sidebar.button("Скачать логи", key="download_logs_btn")

    # ========== (10) Выгрузка моделей и логов ==========
    st.sidebar.header("10. Выгрузка моделей и логов")
    st.sidebar.button("Скачать все содержимое AutogluonModels", key="download_model_and_logs")

    return page_choice
