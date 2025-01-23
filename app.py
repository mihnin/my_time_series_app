import streamlit as st
import plotly.express as px
import sys
import os
import logging
import pandas as pd

# ========== Импорт наших модулей ==========
from data_processing import load_data, convert_to_timeseries
from forecasting import make_timeseries_dataframe, train_model, forecast
from utils import setup_logger, save_model, load_model, read_logs, MODEL_PATH
from feature_engineering import fill_missing_values, add_russian_holiday_feature

# Библиотека для праздников
import holidays
import datetime

# Метрики (EN->RU)
METRICS_DICT = {
    "SQL (Scaled quantile loss)": "Масштабированная квантильная ошибка",
    "WQL (Weighted quantile loss)": "Взвешенная квантильная ошибка",
    "MAE (Mean absolute error)": "Средняя абсолютная ошибка",
    "MAPE (Mean absolute percentage error)": "Средняя абсолютная процентная ошибка",
    "MASE (Mean absolute scaled error)": "Средняя абсолютная масштабированная ошибка",
    "MSE (Mean squared error)": "Среднеквадратичная ошибка",
    "RMSE (Root mean squared error)": "Корень из среднеквадратичной ошибки",
    "RMSLE (Root mean squared logarithmic error)": "Корень из среднеквадратичной логарифмической ошибки",
    "RMSSE (Root mean squared scaled error)": "Корень из среднеквадратичной масштабированной ошибки",
    "SMAPE (Symmetric mean absolute percentage error)": "Симметричная средняя абсолютная процентная ошибка",
    "WAPE (Weighted absolute percentage error)": "Взвешенная абсолютная процентная ошибка"
}

# Модели
AG_MODELS = {
    "NaiveModel": "Базовая модель: прогноз = последнее наблюдение",
    "SeasonalNaiveModel": "Прогноз = последнее значение той же фазы сезона",
    "AverageModel": "Прогноз = среднее/квантиль",
    "SeasonalAverageModel": "Прогноз = среднее по тем же фазам сезона",
    "ZeroModel": "Прогноз = 0",
    "ETSModel": "Экспоненциальное сглаживание (ETS)",
    "AutoARIMAModel": "Автоматическая ARIMA",
    "AutoETSModel": "Автоматическая ETS",
    "AutoCESModel": "Комплексное экспоненциальное сглаживание (AIC)",
    "ThetaModel": "Theta",
    "ADIDAModel": "Intermittent demand (ADIDA)",
    "CrostonModel": "Intermittent demand (Croston)",
    "IMAPAModel": "Intermittent demand (IMAPA)",
    "NPTSModel": "Non-Parametric Time Series",
    "DeepARModel": "RNN (DeepAR)",
    "DLinearModel": "DLinear (убирает тренд)",
    "PatchTSTModel": "PatchTST (Transformer)",
    "SimpleFeedForwardModel": "Простая полносвязная сеть",
    "TemporalFusionTransformerModel": "LSTM + Transformer (TFT)",
    "TiDEModel": "Time series dense encoder",
    "WaveNetModel": "WaveNet (CNN)",
    "DirectTabularModel": "AutoGluon-Tabular (Direct)",
    "RecursiveTabularModel": "AutoGluon-Tabular (Recursive)",
    "ChronosModel": "Chronos pretrained"
}

#############################
# Вспомогательные функции
#############################
def show_help_page():
    st.title("Справка / Помощь")
    st.markdown("""
    В этом приложении вы можете:
      - Загрузить 2 файла: Train (обяз.) и Forecast (необяз.).
      - Выбрать частоту (freq): auto (пусть AutoGluon сам решает) или D/H/M/etc.
      - Если freq != auto, то мы приводим временной ряд к регулярному сеточному формату: convert_frequency(...)
      - Учитывать праздники, статические признаки, пропуски и т.д.
    """)


#############################
# Основная логика (main)
#############################
def main():
    setup_logger()

    pages = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", pages)
    if choice == "Help":
        show_help_page()
        return

    st.title("AutoGluon Приложение: Выбор freq, праздники, статические фичи")

    # ========== 1. Загрузка файлов ==========
    st.sidebar.header("1. Загрузка данных (Train+Forecast)")
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv","xls","xlsx"], key="train_file")
    forecast_file = st.sidebar.file_uploader("Forecast (необязательно)", type=["csv","xls","xlsx"], key="forecast_file")

    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "df_forecast" not in st.session_state:
        st.session_state["df_forecast"] = None

    if st.sidebar.button("Загрузить данные"):
        if not train_file:
            st.error("Train-файл обязателен!")
        else:
            try:
                ext1 = os.path.splitext(train_file.name)[1].lower()
                if ext1 == ".csv":
                    df_train = pd.read_csv(train_file)
                else:
                    df_train = pd.read_excel(train_file)
                st.session_state["df"] = df_train
                st.success("Train-файл загружен!")
                st.dataframe(df_train.head())

                if forecast_file:
                    ext2 = os.path.splitext(forecast_file.name)[1].lower()
                    if ext2 == ".csv":
                        df_fore = pd.read_csv(forecast_file)
                    else:
                        df_fore = pd.read_excel(forecast_file)
                    st.session_state["df_forecast"] = df_fore
                    st.success("Forecast-файл загружен!")
                    st.dataframe(df_fore.head())
                else:
                    st.session_state["df_forecast"] = None
                    st.info("Forecast не загружен, будем прогнозировать на Train.")

            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")

    # ========== 2. Настройка столбцов (дата, target, id) ==========
    st.sidebar.header("2. Колонки датасета")
    if st.session_state["df"] is not None:
        all_cols = list(st.session_state["df"].columns)
    else:
        all_cols = []

    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"]+all_cols)
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"]+all_cols)
    id_col  = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"]+all_cols)

    st.sidebar.header("Статические признаки (до 3)")
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    static_feats = st.sidebar.multiselect("Статические колонки:", possible_static, default=[])

    use_holidays = st.sidebar.checkbox("Учитывать праздники РФ?", value=False)

    # ========== 3. Обработка пропусков ==========
    st.sidebar.header("3. Обработка пропусков")
    fill_method = st.sidebar.selectbox(
        "Способ заполнения",
        ["None", "Constant=0", "Group mean", "Forward fill"]
    )
    group_cols_for_fill = []
    if fill_method in ["Group mean","Forward fill"]:
        group_cols_for_fill = st.sidebar.multiselect("Колонки для группировки", static_feats)

    # ========== 4. Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    # Предлагаем user выбрать: auto (пусть AutoGluon сам), D, H, M, W...
    freq_options = ["auto (угадать)", "D (день)", "H (час)", "M (месяц)", "B (рабочие дни)"]
    chosen_freq = st.sidebar.selectbox("freq", freq_options, index=0)

    # ========== 5. Метрика, модели, пресет, time_limit ==========
    st.sidebar.header("5. Метрика и модели")

    metrics_list = list(METRICS_DICT.keys())
    def_idx = 4 if "MASE (Mean absolute scaled error)" in metrics_list else 0
    chosen_metric = st.sidebar.selectbox("Метрика", metrics_list, index=def_idx)

    all_models_opt = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_opt]+model_keys
    chosen_models = st.sidebar.multiselect("Модели AutoGluon", model_choices, default=[all_models_opt])

    presets = st.sidebar.selectbox("Presets", ["fast_quality","medium_quality","high_quality","best_quality"], index=1)
    prediction_length = st.sidebar.number_input("prediction_length", min_value=1, max_value=365, value=10)
    time_limit = st.sidebar.number_input("time_limit (sec)", min_value=10, max_value=36000, value=60)

    # Чекбокс “Mean only” / quantiles
    mean_only = st.sidebar.checkbox("Прогнозить только среднее (mean)?", value=False)

    # ========== 6. Обучение ==========
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None

    st.sidebar.header("Обучение модели")
    if st.sidebar.button("Обучить модель"):
        df_train = st.session_state.get("df")
        if df_train is None:
            st.warning("Сначала загрузите Train.")
        else:
            if dt_col=="<нет>" or tgt_col=="<нет>" or id_col=="<нет>":
                st.error("Укажите колонки: дата, target, ID.")
            else:
                try:
                    df2 = df_train.copy()
                    # Преобразуем дату
                    if not pd.api.types.is_datetime64_any_dtype(df2[dt_col]):
                        df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")
                    # Праздники
                    if use_holidays:
                        df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")
                    # Заполнение пропусков
                    df2 = fill_missing_values(df2, fill_method, group_cols_for_fill)
                    # Статические фичи
                    static_df = None
                    if static_feats:
                        tmp = df2[[id_col]+static_feats].drop_duplicates(subset=[id_col])
                        tmp = tmp.rename(columns={id_col:"item_id"}).set_index("item_id",drop=False)
                        static_df = tmp.drop(columns=["item_id"], errors="ignore")

                    # convert_to_timeseries
                    df_ready = convert_to_timeseries(df2, id_col, dt_col, tgt_col, static_df=static_df)
                    ts_df = make_timeseries_dataframe(df_ready)

                    # Если freq != "auto (угадать)", переводим в регулярный формат
                    actual_freq = None
                    if chosen_freq != "auto (угадать)":
                        # Пример: "D (день)" -> "D"
                        freq_short = chosen_freq.split(" ")[0]  # "D", "H", ...
                        from autogluon.timeseries import TimeSeriesDataFrame
                        ts_df = ts_df.convert_frequency(freq_short)
                        ts_df = ts_df.fill_missing_values(method="ffill")  # или forward fill
                        actual_freq = freq_short

                    # Готовим hyperparameters
                    if (len(chosen_models)==1 and chosen_models[0]==all_models_opt) or len(chosen_models)==0:
                        hyperparams = None
                    else:
                        no_star = [m for m in chosen_models if m!=all_models_opt]
                        hyperparams = {m:{} for m in no_star}

                    eval_key = chosen_metric.split(" ")[0]
                    from autogluon.timeseries import TimeSeriesPredictor
                    q_levels = None
                    if mean_only:
                        q_levels = [0.5]

                    # Создаём predictor
                    predictor = TimeSeriesPredictor(
                        target="target",
                        prediction_length=prediction_length,
                        eval_metric=eval_key,
                        freq=actual_freq,   # Если user выбрал freq != auto
                        quantile_levels=q_levels
                    )

                    predictor.fit(
                        train_data=ts_df,
                        time_limit=time_limit,
                        presets=presets,
                        hyperparameters=hyperparams
                    )

                    st.session_state["predictor"] = predictor
                    st.success("Модель обучена!")

                    lb = predictor.leaderboard(ts_df)
                    st.session_state["leaderboard"] = lb
                    st.subheader("Лидерборд")
                    st.dataframe(lb)

                    summ = predictor.fit_summary()
                    st.session_state["fit_summary"] = summ

                    best_model = lb.iloc[0]["model"]
                    best_score = lb.iloc[0]["score_val"]
                    st.info(f"Лучшая модель: {best_model}, score_val={best_score}")

                    with st.expander("fit_summary"):
                        st.text(summ)

                except Exception as ex:
                    st.error(f"Ошибка обучения: {ex}")
                    logging.error(str(ex))

    # ========== Прогноз ==========
    st.sidebar.header("Прогноз")
    if st.sidebar.button("Сделать прогноз"):
        predictor = st.session_state.get("predictor")
        if predictor is None:
            st.warning("Модель не обучена.")
        else:
            df_train = st.session_state.get("df")
            df_fore = st.session_state.get("df_forecast")
            if df_train is None:
                st.error("Нет train данных.")
            else:
                try:
                    if df_fore is not None:
                        st.subheader("Прогноз на FORECAST")
                        df_pred = df_fore.copy()
                    else:
                        st.subheader("Прогноз на TRAIN (т.к. forecast не загружен)")
                        df_pred = df_train.copy()

                    # Та же логика обработки
                    if not pd.api.types.is_datetime64_any_dtype(df_pred[dt_col]):
                        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")
                    if use_holidays:
                        df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")
                    df_pred = fill_missing_values(df_pred, fill_method, group_cols_for_fill)

                    static_df = None
                    if static_feats:
                        tmp = df_pred[[id_col]+static_feats].drop_duplicates(subset=[id_col])
                        tmp = tmp.rename(columns={id_col:"item_id"}).set_index("item_id",drop=False)
                        static_df = tmp.drop(columns=["item_id"], errors="ignore")

                    # Если нет tgt_col, добавляем:
                    if tgt_col not in df_pred.columns:
                        df_pred[tgt_col] = None

                    df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col, static_df=static_df)
                    ts_df = make_timeseries_dataframe(df_prepared)

                    # Если freq != auto, тоже приводим
                    if st.session_state["predictor"] is not None and chosen_freq!="auto (угадать)":
                        freq_short = chosen_freq.split(" ")[0]
                        ts_df = ts_df.convert_frequency(freq_short)
                        ts_df = ts_df.fill_missing_values(method="ffill")

                    preds = forecast(predictor, ts_df)
                    st.session_state["predictions"] = preds

                    st.dataframe(preds.reset_index().head())

                    # Если "0.5" для графиков
                    if "0.5" in preds.columns:
                        preds_df = preds.reset_index()
                        cat_mode_choice = cat_mode
                        if cat_mode_choice=="Прогноз по категориям":
                            item_sums = preds_df.groupby("item_id")["0.5"].sum().sort_values(ascending=False)
                            top_items = item_sums.index[:max_graphs]
                            for it in top_items:
                                subset = preds_df[preds_df["item_id"]==it]
                                fig_ = px.line(subset, x="timestamp", y="0.5", title=f"Прогноз {it}")
                                st.plotly_chart(fig_, use_container_width=True)
                        else:
                            fig_ = px.line(preds_df, x="timestamp", y="0.5", color="item_id",
                                           title="Общий прогноз (0.5)")
                            st.plotly_chart(fig_, use_container_width=True)
                    else:
                        st.warning("Нет колонки '0.5' — возможно, quantiles отключены, либо mean_only=False?")

                except Exception as ex:
                    st.error(f"Ошибка прогноза: {ex}")
                    logging.error(str(ex))

    # ========== Сохранение ==========
    st.sidebar.header("Сохранение/Логи")
    save_path = st.sidebar.text_input("Excel-файл (results.xlsx)", "results.xlsx")
    if st.sidebar.button("Сохранить результаты"):
        try:
            df_train = st.session_state.get("df")
            df_fore = st.session_state.get("df_forecast")
            lb = st.session_state.get("leaderboard")
            preds = st.session_state.get("predictions")

            with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                if df_train is not None:
                    df_train.to_excel(writer, sheet_name="TrainData", index=False)
                if df_fore is not None:
                    df_fore.to_excel(writer, sheet_name="ForecastData", index=False)
                if lb is not None:
                    lb.to_excel(writer, sheet_name="Leaderboard", index=False)
                if preds is not None:
                    preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False)

            st.success(f"Сохранено в {save_path}")
        except Exception as ex:
            st.error(f"Ошибка сохранения: {ex}")

    if st.sidebar.button("Сохранить модель"):
        if st.session_state.get("predictor") is None:
            st.warning("Нет обученной модели.")
        else:
            try:
                save_model(st.session_state["predictor"])
                st.success(f"Модель сохранена в {MODEL_PATH}")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    if st.sidebar.button("Загрузить модель"):
        try:
            st.session_state["predictor"] = load_model()
            st.success("Модель загружена.")
        except Exception as e:
            st.error(f"Ошибка: {e}")

    if st.sidebar.button("Показать логи"):
        logs_ = read_logs()
        st.subheader("Логи")
        st.text(logs_)

if __name__=="__main__":
    main()




