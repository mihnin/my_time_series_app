import streamlit as st
import plotly.express as px
import pandas as pd
import os
import logging

# ========== Импорт наших модулей ==========
from src.data.data_processing import load_data, convert_to_timeseries
from src.features.feature_engineering import fill_missing_values, add_russian_holiday_feature
from src.models.forecasting import make_timeseries_dataframe, forecast
from src.utils.utils import (
    setup_logger,
    read_logs  # нет больше save_model / load_model
)
from autogluon.timeseries import TimeSeriesPredictor

# ----- Словари и константы -----
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
    **В этом приложении вы можете:**
    - Загрузить 2 файла: Train (обяз.) и Forecast (необяз.).
    - Указать колонки с датой, target, ID временного ряда.
    - Выбрать частоту (freq): auto или D/H/M/B/etc.
    - Добавлять статические фичи, учитывать праздники, заполнять пропуски.
    - Обучить модель AutoGluon (TimeSeriesPredictor) и сделать прогноз.
    - Результаты можно сохранить в Excel.  
    **Важно:** модель автоматически сохраняется AutoGluon в папке `AutogluonModels`, 
    откуда вы сможете взять её при необходимости.
    """)

def main():
    setup_logger()

    pages = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", pages)

    if choice == "Help":
        show_help_page()
        return

    st.title("AutoGluon Приложение: Прогнозирование временных рядов")

    # -------- Инициализация SessionState --------
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

    # ========== (1) Загрузка данных ==========
    st.sidebar.header("1. Загрузка данных (Train+Forecast)")
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv","xls","xlsx"], key="train_file")
    forecast_file = st.sidebar.file_uploader("Forecast (необязательно)", type=["csv","xls","xlsx"], key="forecast_file")

    if st.sidebar.button("Загрузить данные"):
        if not train_file:
            st.error("Train-файл обязателен!")
        else:
            try:
                df_train = load_data(train_file)
                st.session_state["df"] = df_train
                st.success("Train-файл загружен!")
                st.dataframe(df_train.head(5))

                if forecast_file:
                    df_fore = load_data(forecast_file)
                    st.session_state["df_forecast"] = df_fore
                    st.success("Forecast-файл загружен!")
                    st.dataframe(df_fore.head(5))
                else:
                    st.session_state["df_forecast"] = None
                    st.info("Forecast не загружен.")
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")

    # ========== (2) Настройка столбцов ==========
    st.sidebar.header("2. Колонки датасета")
    df_current = st.session_state["df"]
    if df_current is not None:
        all_cols = list(df_current.columns)
    else:
        all_cols = []

    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"] + all_cols)
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"] + all_cols)
    id_col  = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"] + all_cols)

    st.sidebar.header("Статические признаки (до 3)")
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    static_feats = st.sidebar.multiselect("Статические колонки:", possible_static, default=[])

    use_holidays = st.sidebar.checkbox("Учитывать праздники РФ?", value=False)

    # Покажем график Target во времени, если дата/таргет выбраны
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
                    title="График целевого признака во времени (по ID)"
                )
            else:
                fig_target = px.line(
                    df_plot.sort_values(dt_col),
                    x=dt_col, y=tgt_col,
                    title="График целевого признака во времени"
                )
            st.subheader("Предварительный анализ Target")
            st.plotly_chart(fig_target, use_container_width=True)
        except Exception as e:
            st.warning(f"Не удалось построить график: {e}")

    # ========== (3) Обработка пропусков ==========
    st.sidebar.header("3. Обработка пропусков")
    fill_method = st.sidebar.selectbox(
        "Способ заполнения пропусков (числовых)",
        ["None", "Constant=0", "Group mean", "Forward fill"]
    )
    group_cols_for_fill = []
    if fill_method in ["Group mean","Forward fill"]:
        group_cols_for_fill = st.sidebar.multiselect(
            "Колонки для группировки при заполнении",
            static_feats
        )

    # ========== (4) Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    freq_options = ["auto (угадать)", "D (день)", "H (час)", "M (месяц)", "B (рабочие дни)"]
    chosen_freq = st.sidebar.selectbox("freq", freq_options, index=0)

    # ========== (5) Метрика, модели, пресет, time_limit ==========
    st.sidebar.header("5. Метрика и модели")
    metrics_list = list(METRICS_DICT.keys())
    def_idx = 0
    if "MASE (Mean absolute scaled error)" in metrics_list:
        def_idx = metrics_list.index("MASE (Mean absolute scaled error)")
    chosen_metric = st.sidebar.selectbox("Метрика", metrics_list, index=def_idx)

    all_models_opt = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_opt]+model_keys
    chosen_models = st.sidebar.multiselect("Модели AutoGluon", model_choices, default=[all_models_opt])

    presets = st.sidebar.selectbox("Presets", ["fast_quality","medium_quality","high_quality","best_quality"], index=1)
    prediction_length = st.sidebar.number_input("prediction_length", min_value=1, max_value=365, value=10)
    time_limit = st.sidebar.number_input("time_limit (sec)", min_value=10, max_value=36000, value=60)
    mean_only = st.sidebar.checkbox("Прогнозировать только среднее (mean)?", value=False)

    # ========== (Кнопка) Обучить модель ==========
    st.sidebar.header("Обучение модели")
    if st.sidebar.button("Обучить модель"):
        df_train = st.session_state.get("df")
        if df_train is None:
            st.warning("Сначала загрузите Train!")
        else:
            if dt_col=="<нет>" or tgt_col=="<нет>" or id_col=="<нет>":
                st.error("Укажите колонки: дата, target, ID!")
            else:
                try:
                    df2 = df_train.copy()
                    df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")

                    # Праздники
                    if use_holidays:
                        df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")

                    # Пропуски
                    df2 = fill_missing_values(df2, fill_method, group_cols_for_fill)

                    # Формируем static_df (содержит колонку item_id)
                    static_df = None
                    if static_feats:
                        tmp = df2[[id_col] + static_feats].drop_duplicates(subset=[id_col]).copy()
                        tmp.rename(columns={id_col: "item_id"}, inplace=True)
                        static_df = tmp

                    # Основной df для TimeSeries
                    df_ready = convert_to_timeseries(df2, id_col, dt_col, tgt_col)

                    # Создаём TimeSeriesDataFrame
                    ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)

                    # Приведение к freq, если выбрано
                    actual_freq = None
                    if chosen_freq != "auto (угадать)":
                        freq_short = chosen_freq.split(" ")[0]
                        ts_df = ts_df.convert_frequency(freq_short)
                        ts_df = ts_df.fill_missing_values(method="ffill")
                        actual_freq = freq_short

                    # Hyperparams
                    if (len(chosen_models) == 1 and chosen_models[0] == all_models_opt) or len(chosen_models) == 0:
                        hyperparams = None
                    else:
                        no_star = [m for m in chosen_models if m != all_models_opt]
                        hyperparams = {m:{} for m in no_star}

                    eval_key = chosen_metric.split(" ")[0]
                    q_levels = [0.5] if mean_only else None

                    st.info("Начинаем обучение...")
                    predictor = TimeSeriesPredictor(
                        target="target",
                        prediction_length=prediction_length,
                        eval_metric=eval_key,
                        freq=actual_freq,
                        quantile_levels=q_levels
                    )

                    # Во время fit AutoGluon сам сохранит модель в папку AutogluonModels
                    predictor.fit(
                        train_data=ts_df,
                        time_limit=time_limit,
                        presets=presets,
                        hyperparameters=hyperparams
                    )
                    st.session_state["predictor"] = predictor
                    st.success("Модель успешно обучена!")

                    # Лидерборд
                    lb = predictor.leaderboard(ts_df)
                    st.session_state["leaderboard"] = lb
                    st.subheader("Лидерборд (Leaderboard)")
                    st.dataframe(lb)

                    # fit_summary
                    summ = predictor.fit_summary()
                    st.session_state["fit_summary"] = summ

                    best_model = lb.iloc[0]["model"]
                    best_score = lb.iloc[0]["score_val"]
                    st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")

                    with st.expander("Fit Summary"):
                        st.text(summ)

                except Exception as ex:
                    st.error(f"Ошибка обучения: {ex}")
                    logging.error(str(ex))

    # ========== (Кнопка) Прогноз ==========
    st.sidebar.header("Прогноз")
    if st.sidebar.button("Сделать прогноз"):
        predictor = st.session_state.get("predictor")
        if predictor is None:
            st.warning("Сначала обучите модель!")
        else:
            df_fore = st.session_state.get("df_forecast")
            df_train = st.session_state.get("df")

            if df_train is None:
                st.error("Нет train данных, загрузите заново!")
            else:
                try:
                    if df_fore is not None:
                        st.subheader("Прогноз на FORECAST")
                        df_pred = df_fore.copy()
                    else:
                        st.subheader("Прогноз на TRAIN (т.к. forecast не загружен)")
                        df_pred = df_train.copy()

                    df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")

                    if use_holidays:
                        df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")

                    df_pred = fill_missing_values(df_pred, fill_method, group_cols_for_fill)

                    static_df = None
                    if static_feats:
                        tmp = df_pred[[id_col] + static_feats].drop_duplicates(subset=[id_col]).copy()
                        tmp.rename(columns={id_col: "item_id"}, inplace=True)
                        static_df = tmp

                    if tgt_col not in df_pred.columns:
                        df_pred[tgt_col] = None

                    df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col)
                    ts_df = make_timeseries_dataframe(df_prepared, static_df=static_df)

                    if chosen_freq != "auto (угадать)":
                        freq_short = chosen_freq.split(" ")[0]
                        ts_df = ts_df.convert_frequency(freq_short)
                        ts_df = ts_df.fill_missing_values(method="ffill")

                    preds = forecast(predictor, ts_df)
                    st.session_state["predictions"] = preds

                    st.subheader("Предсказанные значения (первые строки)")
                    st.dataframe(preds.reset_index().head())

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
                        st.info("Нет колонки '0.5' (mean_only=False или квантильные отключены).")

                except Exception as ex:
                    st.error(f"Ошибка прогноза: {ex}")
                    logging.error(str(ex))

    # ========== (Кнопка) Сохранение результатов, Логи (Без сохранения модели!) ==========
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

    if st.sidebar.button("Показать логи"):
        logs_ = read_logs()
        st.subheader("Логи")
        st.text(logs_)

if __name__ == "__main__":
    main()
