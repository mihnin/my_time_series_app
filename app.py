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
    
    **Формат**: CSV или Excel, минимум 3 колонки: `item_id`, `timestamp`, `target`.
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
    st.sidebar.header("1. Загрузка данных")
    uploaded_file = st.sidebar.file_uploader("Загрузите CSV/Excel", type=["csv", "xls", "xlsx"])

    # 2. Настройки столбцов
    st.sidebar.header("2. Настройки столбцов")
    id_col = st.sidebar.text_input("ID серии", value="item_id")
    ts_col = st.sidebar.text_input("Колонка даты", value="timestamp")
    target_col = st.sidebar.text_input("Целевой столбец", value="target")

    # 3. Метрика (из словаря)
    st.sidebar.header("3. Метрика (EN→RU)")
    metrics_list = list(METRICS_DICT.keys())  # ["SQL (Scaled quantile loss)", "WQL...", ...]
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

    # 5. Пресеты
    st.sidebar.header("5. Пресет")
    presets = st.sidebar.selectbox(
        "Presets",
        ["fast_quality", "medium_quality", "high_quality", "best_quality"],
        index=1
    )

    # 6. Прочее
    st.sidebar.header("6. Прочие настройки")
    prediction_length = st.sidebar.number_input("Длина прогноза", min_value=1, max_value=365, value=30)
    time_limit = st.sidebar.number_input("Лимит времени (сек)", min_value=10, max_value=36000, value=300)

    # Режим категорий
    st.sidebar.header("7. Категориальные признаки")
    cat_mode = st.sidebar.selectbox(
        "Вариант",
        ["Игнорировать категории", "Прогноз по категориям"]
    )
    max_graphs = st.sidebar.number_input("Сколько топ-графиков рисовать", min_value=1, max_value=10, value=5)

    # Состояния
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None

    # Кнопка: Загрузить данные
    if st.sidebar.button("Загрузить данные"):
        if not uploaded_file:
            st.warning("Нет файла для загрузки.")
        else:
            try:
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                if ext == ".csv":
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                st.session_state["df"] = df

                st.success("Данные загружены!")
                st.subheader("Исходные данные (с целевым столбцом слева)")
                if target_col in df.columns:
                    cols_order = [target_col] + [c for c in df.columns if c != target_col]
                    st.dataframe(df[cols_order].head(10))
                else:
                    st.dataframe(df.head(10))

                # Доп. сводная инфа
                rows, cols_ = df.shape
                st.write(f"**Число строк**: {rows}, **Число столбцов**: {cols_}")

                # Пропуски
                st.write("**Пропущенные значения (по каждому столбцу):**")
                st.dataframe(df.isnull().sum().to_frame("MissingCount"))

                # Числовые столбцы
                numeric_cols = df.select_dtypes(include=["int", "float"]).columns
                if len(numeric_cols) > 0:
                    st.write("**Статистика по числовым столбцам:**")
                    desc = df[numeric_cols].describe().T
                    st.dataframe(desc)
                else:
                    st.write("Числовых столбцов не найдено.")

                # Категориальные
                cat_cols = df.select_dtypes(include=["object", "category"]).columns
                if len(cat_cols) > 0:
                    st.write("**Категориальные столбцы и число уникальных:**")
                    cat_info = {c: df[c].nunique() for c in cat_cols}
                    st.dataframe(pd.DataFrame.from_dict(cat_info, orient="index", columns=["UniqueCount"]))
                else:
                    st.write("Нет категориальных столбцов.")

                # График (общий)
                if ts_col in df.columns and target_col in df.columns:
                    st.subheader("График всего временного ряда")
                    fig = px.line(df, x=ts_col, y=target_col, title="Исходный временной ряд (общий)")
                    st.plotly_chart(fig, use_container_width=True)

            except Exception as ex:
                st.error(f"Ошибка при загрузке: {ex}")
                logging.error(str(ex))

    # Кнопка: Обучить
    if st.sidebar.button("Обучить модель"):
        if st.session_state["df"] is None:
            st.warning("Сначала загрузите данные.")
        else:
            try:
                df = st.session_state["df"]
                df_prepared = convert_to_timeseries(df, id_col, ts_col, target_col)
                ts_df = make_timeseries_dataframe(df_prepared)

                # Извлекаем "короткое" имя метрики
                # Напр. "MASE (Mean absolute scaled error)" -> "MASE"
                metric_key = chosen_metric.split(" ")[0]

                # Формируем hyperparameters на основе выбора моделей
                # Если пользователь выбрал "* (все)" или ничего не выбрал, даём None (т.е. используем всё)
                if (len(chosen_models) == 1 and chosen_models[0] == all_models_option) or len(chosen_models) == 0:
                    hyperparams = None
                else:
                    # Составим словарь: {"NaiveModel": {}, "ETSModel": {}}
                    # Только для выбранных (исключая "* (все)")
                    chosen_no_star = [m for m in chosen_models if m != all_models_option]
                    hyperparams = {m: {} for m in chosen_no_star}

                predictor = train_model(
                    train_ts_df=ts_df,
                    target="target",
                    prediction_length=prediction_length,
                    time_limit=time_limit,
                    presets=presets,
                    eval_metric=metric_key,  # напр. "MASE"
                    known_covariates=None,
                    hyperparameters=hyperparams
                )
                st.session_state["predictor"] = predictor
                st.success("Модель(и) успешно обучена!")

                # Лидерборд
                lb_df = predictor.leaderboard(ts_df)
                st.session_state["leaderboard"] = lb_df
                st.subheader("Лидерборд")
                st.dataframe(lb_df)

                # fit_summary
                fit_sum = predictor.fit_summary()
                st.session_state["fit_summary"] = fit_sum

                # Лучшая модель
                best_model = lb_df.iloc[0]["model"]
                best_score = lb_df.iloc[0]["score_val"]
                st.info(f"**Лучшая модель**: {best_model} со score_val={best_score}")

                with st.expander("fit_summary (подробности)"):
                    st.text(fit_sum)

            except Exception as ex:
                st.error(f"Ошибка обучения: {ex}")
                logging.error(str(ex))

    # Прогноз
    st.sidebar.header("Прогноз")
    if st.sidebar.button("Сделать прогноз"):
        if st.session_state["predictor"] is None:
            st.warning("Сначала обучите модель.")
        else:
            df = st.session_state["df"]
            predictor = st.session_state["predictor"]
            try:
                df_prep = convert_to_timeseries(df, id_col, ts_col, target_col)
                ts_df = make_timeseries_dataframe(df_prep)
                preds = forecast(predictor, ts_df)

                st.session_state["predictions"] = preds
                st.subheader("Прогноз")
                preds_df = preds.reset_index()
                st.write(preds_df.head())

                # Если есть квантиль 0.5 — берём как "медиану"
                if "0.5" in preds_df.columns:
                    # Если выбрано "Прогноз по категориям", рисуем топ-N item_id
                    if cat_mode == "Прогноз по категориям":
                        # Суммируем 0.5 по item_id
                        item_sums = preds_df.groupby("item_id")["0.5"].sum().sort_values(ascending=False)
                        top_items = item_sums.index[:max_graphs]
                        for it in top_items:
                            subset = preds_df[preds_df["item_id"] == it]
                            fig_ = px.line(subset, x="timestamp", y="0.5",
                                           title=f"Прогноз (0.5) для {it}")
                            st.plotly_chart(fig_, use_container_width=True)
                    else:
                        # Игнорируем категории — один общий график
                        fig_ = px.line(preds_df, x="timestamp", y="0.5",
                                       color="item_id",
                                       title="Общий прогноз (медиана)")
                        st.plotly_chart(fig_, use_container_width=True)
                else:
                    st.warning("Не найден квантиль '0.5' в прогнозе. Попробуйте другую колонку (напр. 'mean').")

            except Exception as ex:
                st.error(f"Ошибка при прогнозировании: {ex}")
                logging.error(str(ex))

    # Сохранение
    st.sidebar.header("Сохранение и логи")

    save_path = st.sidebar.text_input("Путь для результатов (Excel)", "results.xlsx")
    if st.sidebar.button("Сохранить результаты"):
        if st.session_state["df"] is None:
            st.warning("Нет данных.")
        else:
            try:
                df_orig = st.session_state["df"]
                lb = st.session_state["leaderboard"]
                preds = st.session_state["predictions"]
                with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                    df_orig.to_excel(writer, sheet_name="RawData", index=False)
                    if lb is not None:
                        lb.to_excel(writer, sheet_name="Leaderboard", index=False)
                    if preds is not None:
                        preds.reset_index().to_excel(writer, sheet_name="Forecast", index=False)
                st.success(f"Сохранено в {save_path}")
            except Exception as ex:
                st.error(f"Ошибка сохранения: {ex}")

    # Кнопки сохранить/загрузить модель
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

    # Показ логов
    if st.sidebar.button("Показать логи"):
        logs = read_logs()
        st.subheader("Логи")
        st.text(logs)


if __name__ == "__main__":
    main()
