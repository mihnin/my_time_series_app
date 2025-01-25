# app.py

import streamlit as st
import plotly.express as px
import pandas as pd
import logging
import shutil
import yaml
import os

# Импорт AutoGluon TimeSeriesPredictor
from autogluon.timeseries import TimeSeriesPredictor

# Импорт необходимых модулей из src (пример, поправьте пути при необходимости)
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
from help_page import show_help_page  # <-- поправьте путь, если нужно

# ========== Загрузка конфигурации из YAML ==========

CONFIG_PATH = "config/config.yaml"

def load_config(path: str):
    """Читает YAML-конфиг и возвращает словари METRICS_DICT и AG_MODELS."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл конфигурации {path} не найден.")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    metrics_dict = data.get("metrics_dict", {})
    ag_models = data.get("ag_models", {})
    return metrics_dict, ag_models

METRICS_DICT, AG_MODELS = load_config(CONFIG_PATH)


def main():
    setup_logger()
    logging.info("=== Запуск приложения Streamlit (main) ===")

    pages = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", pages, key="page_choice")
    logging.info(f"Выбрана страница: {choice}")

    if choice == "Help":
        show_help_page()
        return

    st.title("AutoGluon Приложение: Прогнозирование временных рядов")

    # -- Инициализируем переменные
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "df_forecast" not in st.session_state:
        st.session_state["df_forecast"] = None
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
    if "static_df_fore" not in st.session_state:
        st.session_state["static_df_fore"] = None

    # ========== 1. Загрузка ==========
    st.sidebar.header("1. Загрузка данных")
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv","xls","xlsx"], key="train_file_uploader")
    forecast_file = st.sidebar.file_uploader("Forecast (необязательно)", type=["csv","xls","xlsx"], key="forecast_file_uploader")

    if st.sidebar.button("Загрузить данные", key="load_data_btn"):
        logging.info("Нажата кнопка 'Загрузить данные'")
        if not train_file:
            st.error("Train-файл обязателен!")
            logging.warning("Train-файл не загружен (обязателен).")
        else:
            try:
                logging.info(f"Пытаемся прочитать Train-файл: {train_file.name}")
                df_train = load_data(train_file)
                st.session_state["df"] = df_train
                st.success("Train-файл загружен!")
                st.dataframe(df_train.head())

                st.subheader("Статистика Train")
                show_dataset_stats(df_train)

                if forecast_file:
                    logging.info(f"Пытаемся прочитать Forecast-файл: {forecast_file.name}")
                    df_fore = load_data(forecast_file)
                    st.session_state["df_forecast"] = df_fore
                    st.success("Forecast-файл загружен!")
                    st.dataframe(df_fore.head())
                else:
                    st.session_state["df_forecast"] = None
                    st.info("Forecast не загружен.")

            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                logging.error(f"Ошибка загрузки данных: {e}")

    # ========== 2. Настройка столбцов ==========
    st.sidebar.header("2. Колонки датасета")

    df_current = st.session_state["df"]
    if df_current is not None:
        all_cols = list(df_current.columns)
    else:
        all_cols = []

    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"] + all_cols, key="dt_col_key")
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"] + all_cols, key="tgt_col_key")
    id_col  = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"] + all_cols, key="id_col_key")

    st.sidebar.header("Статические признаки (до 3)")
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    static_feats = st.sidebar.multiselect("Статические колонки:", possible_static, default=[], key="static_feats_key")

    use_holidays = st.sidebar.checkbox("Учитывать праздники РФ?", value=False, key="use_holidays_key")

    # Логируем выбранные значения
    logging.info(f"Пользователь задал dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}, "
                 f"static_feats={static_feats}, use_holidays={use_holidays}")

    # Предварительный график
    if df_current is not None and dt_col != "<нет>" and tgt_col != "<нет>":
        try:
            df_plot = df_current.copy()
            df_plot[dt_col] = pd.to_datetime(df_plot[dt_col], errors="coerce")
            df_plot = df_plot.dropna(subset=[dt_col])

            if id_col != "<нет>":
                fig_target = px.line(df_plot.sort_values(dt_col),
                                     x=dt_col, y=tgt_col,
                                     color=id_col,
                                     title="График Target по ID")
            else:
                fig_target = px.line(df_plot.sort_values(dt_col),
                                     x=dt_col, y=tgt_col,
                                     title="График Target (без ID)")

            st.subheader("Предварительный анализ Target")
            st.plotly_chart(fig_target, use_container_width=True)
        except Exception as e:
            st.warning(f"Не удалось построить график: {e}")
            logging.warning(f"Ошибка при построении предварительного графика: {e}")

    # ========== 3. Обработка пропусков ==========
    st.sidebar.header("3. Обработка пропусков")
    fill_method = st.sidebar.selectbox("Способ заполнения пропусков",
                                       ["None", "Constant=0", "Group mean", "Forward fill"],
                                       key="fill_method_key")
    group_cols_for_fill = []
    if fill_method in ["Group mean","Forward fill"]:
        group_cols_for_fill = st.sidebar.multiselect(
            "Колонки для группировки",
            static_feats,
            key="group_cols_for_fill_key"
        )

    logging.info(f"Выбран метод заполнения пропусков: {fill_method}, group_cols_for_fill={group_cols_for_fill}")

    # ========== 4. Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    freq_options = ["auto (угадать)", "D (день)", "H (час)", "M (месяц)", "B (рабочие дни)"]
    chosen_freq = st.sidebar.selectbox("freq", freq_options, index=0, key="freq_key")
    logging.info(f"Выбрана частота: {chosen_freq}")

    # ========== 5. Метрика, пресет, модели, time_limit ==========
    st.sidebar.header("5. Метрика и модели")
    metrics_list = list(METRICS_DICT.keys())
    default_metric_idx = 0
    if "MASE (Mean absolute scaled error)" in metrics_list:
        default_metric_idx = metrics_list.index("MASE (Mean absolute scaled error)")
    chosen_metric = st.sidebar.selectbox("Метрика", metrics_list, index=default_metric_idx, key="metric_key")

    all_models_opt = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_opt] + model_keys
    chosen_models = st.sidebar.multiselect("Модели AutoGluon", model_choices, default=[all_models_opt], key="models_key")

    presets_list = ["fast_training","medium_quality","high_quality","best_quality"]
    presets = st.sidebar.selectbox("Presets", presets_list, index=1, key="presets_key")

    prediction_length = st.sidebar.number_input("prediction_length", 1, 365, 10, key="prediction_length_key")
    time_limit = st.sidebar.number_input("time_limit (sec)", 10, 36000, 60, key="time_limit_key")
    mean_only = st.sidebar.checkbox("Прогнозировать только среднее (mean)?", value=False, key="mean_only_key")

    logging.info(
        f"Метрика: {chosen_metric}, модели: {chosen_models}, presets: {presets}, "
        f"prediction_length={prediction_length}, time_limit={time_limit}, mean_only={mean_only}"
    )

    # ========== Кнопка обучения ==========
    st.sidebar.header("6. Обучение модели")
    if st.sidebar.button("Обучить модель", key="fit_model_btn"):
        logging.info("Нажата кнопка 'Обучить модель'")
        df_train = st.session_state.get("df")
        dt_col = st.session_state.get("dt_col_key")
        tgt_col = st.session_state.get("tgt_col_key")
        id_col  = st.session_state.get("id_col_key")

        if df_train is None:
            st.warning("Сначала загрузите Train!")
            logging.warning("Попытка обучения без Train-данных.")
        else:
            if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
                st.error("Выберите корректно колонки: дата, target, ID!")
                logging.error("Некорректные столбцы для обучения.")
            else:
                try:
                    # Очищаем папку AutogluonModels перед обучением, чтобы не накапливались старые модели
                    logging.info("Очищаем папку 'AutogluonModels' перед обучением...")
                    shutil.rmtree("AutogluonModels", ignore_errors=True)

                    use_holidays_val = st.session_state.get("use_holidays_key", False)
                    fill_method_val = st.session_state.get("fill_method_key", "None")
                    group_cols_fill_val = st.session_state.get("group_cols_for_fill_key", [])
                    freq_val = st.session_state.get("freq_key", "auto (угадать)")
                    chosen_metric_val = st.session_state.get("metric_key")
                    chosen_models_val = st.session_state.get("models_key")
                    presets_val = st.session_state.get("presets_key", "medium_quality")
                    mean_only_val = st.session_state.get("mean_only_key", False)

                    df2 = df_train.copy()
                    df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")

                    if use_holidays_val:
                        df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")

                    df2 = fill_missing_values(df2, fill_method_val, group_cols_fill_val)
                    st.session_state["df"] = df2  # обновим в сессии

                    # Статические фичи
                    static_feats_val = st.session_state.get("static_feats_key", [])
                    static_df = None
                    if static_feats_val:
                        tmp = df2[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
                        tmp.rename(columns={id_col: "item_id"}, inplace=True)
                        static_df = tmp

                    df_ready = convert_to_timeseries(df2, id_col, dt_col, tgt_col)
                    ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)

                    if ts_df.static_features is not None and len(ts_df.static_features) > 0:
                        st.session_state["static_df_train"] = ts_df.static_features.copy()
                    else:
                        st.session_state["static_df_train"] = None

                    actual_freq = None
                    if freq_val != "auto (угадать)":
                        freq_short = freq_val.split(" ")[0]
                        ts_df = ts_df.convert_frequency(freq_short)
                        ts_df = ts_df.fill_missing_values(method="ffill")
                        actual_freq = freq_short

                    # Настраиваем hyperparams (если выбрано не "все модели")
                    if (len(chosen_models_val) == 1 and chosen_models_val[0] == all_models_opt) or len(chosen_models_val) == 0:
                        hyperparams = None
                    else:
                        no_star = [m for m in chosen_models_val if m != all_models_opt]
                        hyperparams = {m:{} for m in no_star}

                    eval_key = chosen_metric_val.split(" ")[0]
                    q_levels = [0.5] if mean_only_val else None

                    # ВАЖНО: Используем 'path' вместо 'save_path'
                    predictor = TimeSeriesPredictor(
                        target="target",
                        prediction_length=prediction_length,
                        eval_metric=eval_key,
                        freq=actual_freq,
                        quantile_levels=q_levels,
                        path="AutogluonModels/TimeSeriesModel"  # <-- Исправленный параметр
                    )

                    st.info("Начинаем обучение...")
                    logging.info("Начинаем обучение модели AutoGluon.")
                    try:
                        predictor.fit(
                            train_data=ts_df,
                            time_limit=time_limit,
                            presets=presets_val,
                            hyperparameters=hyperparams
                        )
                    except ValueError as e:
                        if "cannot be inferred" in str(e):
                            st.error("AutoGluon не смог определить freq='auto'. Укажите freq вручную.")
                            logging.error("AutoGluon не смог определить частоту (freq='auto').")
                            raise
                        else:
                            raise

                    st.session_state["predictor"] = predictor
                    st.success("Модель успешно обучена!")
                    logging.info("Модель успешно обучена.")

                    lb = predictor.leaderboard(ts_df)
                    st.session_state["leaderboard"] = lb
                    st.subheader("Лидерборд (Leaderboard)")
                    st.dataframe(lb)

                    summ = predictor.fit_summary()
                    st.session_state["fit_summary"] = summ

                    best_model = lb.iloc[0]["model"]
                    best_score = lb.iloc[0]["score_val"]
                    st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")
                    logging.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")

                    with st.expander("Fit Summary"):
                        st.text(summ)

                except Exception as ex:
                    st.error(f"Ошибка обучения: {ex}")
                    logging.error(f"Ошибка обучения: {ex}")

    # ========== 7. Кнопка "Сделать прогноз" ==========
    st.sidebar.header("7. Прогноз")
    if st.sidebar.button("Сделать прогноз", key="predict_btn"):
        logging.info("Нажата кнопка 'Сделать прогноз'")
        predictor = st.session_state.get("predictor")
        if predictor is None:
            st.warning("Сначала обучите модель!")
            logging.warning("Попытка сделать прогноз без обученной модели.")
        else:
            dt_col = st.session_state.get("dt_col_key")
            tgt_col = st.session_state.get("tgt_col_key")
            id_col  = st.session_state.get("id_col_key")

            if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
                st.error("Проверьте, что выбраны колонки: дата, target, ID!")
                logging.error("Прогноз невозможен — не указаны нужные столбцы.")
            else:
                df_fore = st.session_state.get("df_forecast")
                df_train = st.session_state.get("df")

                if df_train is None:
                    st.error("Нет train данных!")
                    logging.error("Прогноз невозможен — нет train-данных.")
                else:
                    try:
                        # Если нет forecast-файла, делаем прогноз на train
                        if df_fore is not None:
                            st.subheader("Прогноз на FORECAST")
                            df_pred = df_fore.copy()
                        else:
                            st.subheader("Прогноз на TRAIN (т.к. forecast не загружен)")
                            df_pred = df_train.copy()

                        # Праздники, пропуски
                        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")
                        if st.session_state.get("use_holidays_key", False):
                            df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")
                        df_pred = fill_missing_values(
                            df_pred,
                            st.session_state.get("fill_method_key","None"),
                            st.session_state.get("group_cols_for_fill_key",[])
                        )

                        if df_fore is not None:
                            st.session_state["df_forecast"] = df_pred
                        else:
                            st.session_state["df"] = df_pred

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

                        if ts_df.static_features is not None and len(ts_df.static_features) > 0:
                            st.session_state["static_df_fore"] = ts_df.static_features.copy()
                        else:
                            st.session_state["static_df_fore"] = None

                        freq_val = st.session_state.get("freq_key", "auto (угадать)")
                        if freq_val != "auto (угадать)":
                            freq_short = freq_val.split(" ")[0]
                            ts_df = ts_df.convert_frequency(freq_short)
                            ts_df = ts_df.fill_missing_values(method="ffill")

                        preds = forecast(predictor, ts_df)
                        st.session_state["predictions"] = preds

                        st.subheader("Предсказанные значения (первые строки)")
                        st.dataframe(preds.reset_index().head())

                        # Пример графиков
                        if "0.5" in preds.columns:
                            preds_df = preds.reset_index().rename(columns={"0.5": "prediction"})
                            unique_ids = preds_df["item_id"].unique()
                            st.subheader("Графики прогноза (0.5) по первым категориям")
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
                            st.info("Нет колонки '0.5' — возможно mean_only=False или квантили выключены.")

                        logging.info("Прогноз успешно выполнен.")
                    except Exception as ex:
                        st.error(f"Ошибка прогноза: {ex}")
                        logging.error(f"Ошибка прогноза: {ex}")

    # ========== 8. Сохранение результатов ==========
    st.sidebar.header("8. Сохранение результатов прогноза")
    save_path = st.sidebar.text_input("Excel-файл", "results.xlsx", key="save_path_key")
    if st.sidebar.button("Сохранить результаты", key="save_btn"):
        logging.info("Нажата кнопка 'Сохранить результаты'")
        try:
            df_train = st.session_state.get("df")
            df_fore = st.session_state.get("df_forecast")
            lb = st.session_state.get("leaderboard")
            preds = st.session_state.get("predictions")
            stt_train = st.session_state.get("static_df_train")
            stt_fore  = st.session_state.get("static_df_fore")

            import openpyxl
            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                if df_train is not None:
                    df_train.to_excel(writer, sheet_name="TrainData", index=False)
                if df_fore is not None:
                    df_fore.to_excel(writer, sheet_name="ForecastData", index=False)
                if lb is not None:
                    lb.to_excel(writer, sheet_name="Leaderboard", index=False)
                if preds is not None:
                    preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False)
                if stt_train is not None and not stt_train.empty:
                    stt_train.to_excel(writer, sheet_name="StaticTrainFeatures")
                if stt_fore is not None and not stt_fore.empty:
                    stt_fore.to_excel(writer, sheet_name="StaticForeFeatures")

            st.success(f"Сохранено в {save_path}")
            logging.info(f"Результаты сохранены в файл {save_path}")
        except Exception as ex:
            st.error(f"Ошибка сохранения: {ex}")
            logging.error(f"Ошибка сохранения результатов: {ex}")

    # ========== 9. Показ/Выгрузка логов ==========
    st.sidebar.header("9. Логи приложения")
    if st.sidebar.button("Показать логи", key="show_logs_btn"):
        logs_ = read_logs()
        st.subheader("Логи")
        st.text(logs_)

    # Кнопка для выгрузки логов обучения AutoGluon, если нужны
    st.sidebar.header("Выгрузка логов обучения модели")
    if st.sidebar.button("Скачать логи модели", key="download_model_logs"):
        # Путь к папке с моделью
        model_folder = "AutogluonModels/TimeSeriesModel"
        if not os.path.exists(model_folder):
            st.error("Папка модели не найдена. Сначала обучите модель.")
            logging.warning("Папка модели не найдена при попытке скачать логи.")
        else:
            # Найдём подпапку вида "TimeSeriesModel\ag-[дата]_...". Обычно там logs.
            subfolders = [f.path for f in os.scandir(model_folder) if f.is_dir()]
            if not subfolders:
                st.error("В папке модели нет подпапок с логами.")
            else:
                # Берем самую свежую подпапку (или любую первую)
                subfolders.sort(key=os.path.getmtime, reverse=True)
                logs_path = os.path.join(subfolders[0], "logs")
                if not os.path.exists(logs_path):
                    st.error("Не найден каталог 'logs' в папке модели.")
                else:
                    import zipfile
                    import io

                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for root, dirs, files in os.walk(logs_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, start=logs_path)
                                zipf.write(file_path, arcname=arcname)

                    zip_buf.seek(0)
                    st.download_button(
                        label="Скачать zip с логами модели",
                        data=zip_buf,
                        file_name="model_logs.zip",
                        mime="application/zip"
                    )
                    logging.info("Пользователь скачал логи модели.")


if __name__ == "__main__":
    main()



