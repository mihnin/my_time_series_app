import streamlit as st
import plotly.express as px
import sys
import os
import logging
import pandas as pd

from data_processing import load_data, convert_to_timeseries
from forecasting import make_timeseries_dataframe, train_model, forecast
from utils import setup_logger, save_model, load_model, read_logs, MODEL_PATH

# ========== Пример словаря МЕТРИК (EN->RU) ==========
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

# ========== Пример списка моделей AutoGluon ==========
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

# (Опционально) проверка conda-окружения
if not os.path.exists(os.path.join(sys.prefix, 'conda-meta')):
    st.warning("⚠️ Conda окружение не активировано! Запустите команду:")
    st.code("conda activate my_time_series_app")

setup_logger()

def show_help_page():
    st.title("Справка / Помощь")
    st.markdown("""
    **Как загружать данные** — см. инструкцию.
    
    **Обязательный файл**: для обучения (train).  
    **Необязательный файл**: для прогноза (forecast) — может не содержать target, 
    его значения спрогнозирует обученная модель.  

    **Формат**: CSV или Excel, минимум 3 колонки: `item_id`, `timestamp`, `target` (для train).  
    ...
    """)

def main():
    page_options = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", page_options)
    if choice == "Help":
        show_help_page()
        return

    # 1. Загрузка
    st.title("Расширенное приложение для прогноза временных рядов (AutoGluon)")

    st.sidebar.header("1. Загрузка данных (Train + Forecast)")
    # (1) Обязательный (train)
    uploaded_file = st.sidebar.file_uploader("Тренировочный CSV/Excel (обязательно)", type=["csv", "xls", "xlsx"], key="train_file")
    # (2) Необязательный (forecast)
    forecast_file = st.sidebar.file_uploader("Данные для прогноза (необязательно)", type=["csv", "xls", "xlsx"], key="forecast_file")

    # Одна кнопка «Загрузить данные»
    if st.sidebar.button("Загрузить данные"):
        if not uploaded_file:
            st.error("Файл для обучения не выбран! Невозможно обучить модель.")
        else:
            # Читаем train
            try:
                ext_train = os.path.splitext(uploaded_file.name)[1].lower()
                if ext_train == ".csv":
                    df_train = pd.read_csv(uploaded_file)
                else:
                    df_train = pd.read_excel(uploaded_file)

                st.session_state["df"] = df_train
                st.success("Тренировочные данные (Train) загружены!")
                st.write("**Train (первые строки):**")
                st.dataframe(df_train.head())

                # EDA и график, как было
                rows, cols_ = df_train.shape
                st.write(f"**Число строк (train)**: {rows}, **Число столбцов**: {cols_}")
                st.write("**Пропуски (train) по столбцам:**")
                st.dataframe(df_train.isnull().sum().to_frame("MissingCount"))

                # Если есть forecast_file
                if forecast_file is not None:
                    ext_fore = os.path.splitext(forecast_file.name)[1].lower()
                    if ext_fore == ".csv":
                        df_forecast = pd.read_csv(forecast_file)
                    else:
                        df_forecast = pd.read_excel(forecast_file)

                    st.session_state["df_forecast"] = df_forecast
                    st.success("Данные для прогноза (Forecast) загружены!")
                    st.write("**Forecast (первые строки):**")
                    st.dataframe(df_forecast.head())

                    # Аналогично можно вывести EDA для forecast
                    r2, c2 = df_forecast.shape
                    st.write(f"**Число строк (forecast)**: {r2}, **Число столбцов**: {c2}")
                    st.write("**Пропуски (forecast) по столбцам:**")
                    st.dataframe(df_forecast.isnull().sum().to_frame("MissingCount"))
                else:
                    st.session_state["df_forecast"] = None
                    st.info("Файл для прогноза не выбран. Будем предсказывать на train.")
            
            except Exception as e:
                st.error(f"Ошибка при загрузке: {e}")
                logging.error(str(e))

    # 2. Настройки столбцов
    st.sidebar.header("2. Настройки столбцов")
    id_col = st.sidebar.text_input("ID серии", value="item_id")
    ts_col = st.sidebar.text_input("Колонка даты", value="timestamp")
    target_col = st.sidebar.text_input("Целевой столбец", value="target")

    # 3. Метрика
    st.sidebar.header("3. Метрика (EN→RU)")
    metrics_list = list(METRICS_DICT.keys())
    def_metric_idx = metrics_list.index("MASE (Mean absolute scaled error)") if "MASE (Mean absolute scaled error)" in metrics_list else 0
    chosen_metric = st.sidebar.selectbox("Метрика", metrics_list, index=def_metric_idx)
    st.sidebar.write(f"Описание метрики: {METRICS_DICT[chosen_metric]}")

    # 4. Выбор моделей
    st.sidebar.header("4. Выбор моделей")
    all_models_option = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_option] + model_keys
    chosen_models = st.sidebar.multiselect(
        "Модели для обучения",
        options=model_choices,
        default=[all_models_option]
    )

    # 5. Пресет
    st.sidebar.header("5. Пресет")
    presets = st.sidebar.selectbox(
        "Presets",
        ["fast_quality", "medium_quality", "high_quality", "best_quality"],
        index=1
    )

    # 6. Прочие настройки
    st.sidebar.header("6. Прочие настройки")
    prediction_length = st.sidebar.number_input("Длина прогноза", min_value=1, max_value=365, value=30)
    time_limit = st.sidebar.number_input("Лимит времени (сек)", min_value=10, max_value=36000, value=300)

    # Категориальные + графики
    st.sidebar.header("7. Категориальные признаки")
    cat_mode = st.sidebar.selectbox("Вариант", ["Игнорировать категории", "Прогноз по категориям"])
    max_graphs = st.sidebar.number_input("Сколько топ-графиков рисовать", min_value=1, max_value=10, value=5)

    # Состояния (прогноз, модель и т.д.)
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None

    # Кнопка: Обучить
    st.sidebar.header("Обучение модели")
    if st.sidebar.button("Обучить модель"):
        if "df" not in st.session_state or st.session_state["df"] is None:
            st.warning("Сначала загрузите тренировочные данные (Train).")
        else:
            try:
                df = st.session_state["df"]
                # Метрика (короткое имя)
                metric_key = chosen_metric.split(" ")[0]

                # Формируем hyperparameters
                if (len(chosen_models) == 1 and chosen_models[0] == all_models_option) or len(chosen_models) == 0:
                    hyperparams = None
                else:
                    chosen_no_star = [m for m in chosen_models if m != all_models_option]
                    hyperparams = {m: {} for m in chosen_no_star}

                df_prep = convert_to_timeseries(df, id_col, ts_col, target_col)
                ts_df = make_timeseries_dataframe(df_prep)

                # Обучение
                predictor = train_model(
                    train_ts_df=ts_df,
                    target="target",
                    prediction_length=prediction_length,
                    time_limit=time_limit,
                    presets=presets,
                    eval_metric=metric_key,
                    known_covariates=None,
                    hyperparameters=hyperparams
                )
                st.session_state["predictor"] = predictor
                st.success("Модель(и) успешно обучена!")

                # Лидерборд
                lb = predictor.leaderboard(ts_df)
                st.session_state["leaderboard"] = lb
                st.subheader("Лидерборд")
                st.dataframe(lb)

                # fit_summary
                fit_sum = predictor.fit_summary()
                st.session_state["fit_summary"] = fit_sum

                # Лучшая модель
                best_model = lb.iloc[0]["model"]
                best_score = lb.iloc[0]["score_val"]
                st.info(f"**Лучшая модель**: {best_model} (score_val={best_score})")

                with st.expander("Подробности обучения (fit_summary)"):
                    st.text(fit_sum)

            except Exception as ex:
                st.error(f"Ошибка при обучении: {ex}")
                logging.error(str(ex))

    # Прогноз
    st.sidebar.header("Прогноз")
    if st.sidebar.button("Сделать прогноз"):
        if st.session_state["predictor"] is None:
            st.warning("Нет обученной модели.")
        else:
            predictor = st.session_state["predictor"]
            try:
                # Если загружен forecast_file => делаем прогноз на нём
                if "df_forecast" in st.session_state and st.session_state["df_forecast"] is not None:
                    df_f = st.session_state["df_forecast"].copy()
                    # Если в forecast нет колонки target, создадим пустую (иначе convert_to_timeseries не сработает)
                    if target_col not in df_f.columns:
                        df_f[target_col] = None
                    df_f_prep = convert_to_timeseries(df_f, id_col, ts_col, target_col)
                    ts_fore = make_timeseries_dataframe(df_f_prep)
                    preds = forecast(predictor, ts_fore)
                    st.subheader("Прогноз на данных Forecast:")
                else:
                    # Иначе — старое поведение, прогноз на train
                    df_t = st.session_state["df"].copy()
                    df_t_prep = convert_to_timeseries(df_t, id_col, ts_col, target_col)
                    ts_train = make_timeseries_dataframe(df_t_prep)
                    preds = forecast(predictor, ts_train)
                    st.subheader("Прогноз на тренировочном датасете (т.к. Forecast не загружен).")

                st.session_state["predictions"] = preds
                preds_df = preds.reset_index()
                st.dataframe(preds_df.head())

                # Если есть квантиль 0.5
                if "0.5" in preds_df.columns:
                    if cat_mode == "Прогноз по категориям":
                        item_sums = preds_df.groupby("item_id")["0.5"].sum().sort_values(ascending=False)
                        top_items = item_sums.index[:max_graphs]
                        for it in top_items:
                            subset = preds_df[preds_df["item_id"] == it]
                            fig_ = px.line(subset, x="timestamp", y="0.5", title=f"Прогноз (0.5) для {it}")
                            st.plotly_chart(fig_, use_container_width=True)
                    else:
                        fig_ = px.line(preds_df, x="timestamp", y="0.5", color="item_id", 
                                       title="Общий прогноз (медиана 0.5)")
                        st.plotly_chart(fig_, use_container_width=True)
                else:
                    st.warning("В прогнозах нет колонки '0.5' (квантиль). Попробуйте 'mean' или др.")

            except Exception as ex:
                st.error(f"Ошибка при прогнозе: {ex}")
                logging.error(str(ex))

    # Сохранение / логи
    st.sidebar.header("Сохранение и логи")
    save_path = st.sidebar.text_input("Путь для Excel (результаты)", "results.xlsx")
    if st.sidebar.button("Сохранить результаты"):
        try:
            df_train = st.session_state.get("df")  # train
            df_fore = st.session_state.get("df_forecast")  # forecast
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
            st.success(f"Результаты сохранены в {save_path}")
        except Exception as ex:
            st.error(f"Ошибка при сохранении: {ex}")

    if st.sidebar.button("Сохранить модель"):
        if st.session_state["predictor"] is None:
            st.warning("Нет обученной модели.")
        else:
            try:
                save_model(st.session_state["predictor"])
                st.success(f"Модель сохранена в {MODEL_PATH}")
            except Exception as ex:
                st.error(f"Ошибка: {ex}")

    if st.sidebar.button("Загрузить модель"):
        try:
            st.session_state["predictor"] = load_model()
            st.success("Модель загружена!")
        except Exception as ex:
            st.error(f"Ошибка: {ex}")

    if st.sidebar.button("Показать логи"):
        logs = read_logs()
        st.subheader("Логи")
        st.text(logs)

if __name__ == "__main__":
    main()


