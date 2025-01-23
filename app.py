import streamlit as st
import plotly.express as px
import sys
import os
import logging
import pandas as pd

from data_processing import load_data, convert_to_timeseries
from forecasting import make_timeseries_dataframe, train_model, forecast
from utils import setup_logger, save_model, load_model, read_logs, MODEL_PATH

# Пакет для праздников
import holidays
import datetime

#####################
# Словари метрик и моделей (остаются без изменений)
#####################
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

#####################
# Вспомогательные функции
#####################
def show_help_page():
    st.title("Справка / Помощь")
    st.markdown("""
    **Это приложение** позволяет:  
     - Загружать два файла: TRAIN (обязательно) и FORECAST (необязательно).  
     - Учитывать статические признаки (до 3).  
     - Учитывать праздники России (чекбокс).  
     - Выбирать модели, метрику, способ заполнения пропусков, пресеты и т.п.  
     - Прогноз по train (если forecast не загружен) или по forecast (если он загружен).  
     - Сохранять результаты и модель, просматривать логи.
    """)

def add_russian_holiday_feature(df, date_col="timestamp", holiday_col="russian_holiday"):
    """Добавляем бинарный признак праздника РФ."""
    if date_col not in df.columns:
        st.warning("Колонка даты не найдена, не можем добавить признак праздника.")
        return df
    # Готовим календарь для диапазона лет
    min_year = df[date_col].dt.year.min()
    max_year = df[date_col].dt.year.max()
    ru_h = holidays.country_holidays(country="RU", years=range(min_year, max_year+2))

    def is_holiday(dt):
        return 1.0 if dt.date() in ru_h else 0.0

    df[holiday_col] = df[date_col].apply(is_holiday).astype(float)
    return df

def fill_missing_values(df, method: str = "None", group_cols=None):
    """
    Заполнение пропусков:
      - "Constant=0": всё числовое -> 0
      - "Group mean": по комбинации group_cols (например, store, country)
      - "Forward fill": ffill/bfill
      - "None": ничего не делаем
    """
    if method == "None":
        return df

    numeric_cols = df.select_dtypes(include=["float", "int"]).columns
    # group_cols — список колонок, по которым группируем
    if method == "Constant=0":
        df[numeric_cols] = df[numeric_cols].fillna(0)
        return df

    if method == "Forward fill":
        df = df.sort_values(by=group_cols, na_position="last") if group_cols else df
        df[numeric_cols] = df.groupby(group_cols)[numeric_cols].apply(lambda g: g.ffill().bfill())
        return df

    if method == "Group mean":
        if not group_cols:
            # Если не задано, просто среднее по всей таблице
            for c in numeric_cols:
                df[c] = df[c].fillna(df[c].mean())
        else:
            # Среднее в разрезе (store, country и т.п.)
            df = df.sort_values(by=group_cols, na_position="last")
            for c in numeric_cols:
                df[c] = df.groupby(group_cols)[c].apply(lambda g: g.fillna(g.mean()))
        return df

    return df

#####################
# Основная логика app
#####################
def main():
    page_options = ["Главная", "Help"]
    choice = st.sidebar.selectbox("Навигация", page_options)
    if choice == "Help":
        show_help_page()
        return

    st.title("Приложение AutoGluon: два файла (train+forecast), праздники, статпризнаки")

    # --------- 1. Загрузка данных (Train, Forecast) ---------
    st.sidebar.header("1. Загрузка данных")
    train_file = st.sidebar.file_uploader("Файл TRAIN (обязательно)", type=["csv","xls","xlsx"], key="train_file")
    forecast_file = st.sidebar.file_uploader("Файл FORECAST (необязательно)", type=["csv","xls","xlsx"], key="forecast_file")

    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "df_forecast" not in st.session_state:
        st.session_state["df_forecast"] = None

    if st.sidebar.button("Загрузить данные"):
        if not train_file:
            st.error("TRAIN-файл не выбран — невозможно обучить модель.")
        else:
            try:
                # Считываем train
                ext_tr = os.path.splitext(train_file.name)[1].lower()
                if ext_tr == ".csv":
                    df_train = pd.read_csv(train_file)
                else:
                    df_train = pd.read_excel(train_file)
                st.session_state["df"] = df_train
                st.success("TRAIN-файл загружен!")
                st.write("**Train (первые строки):**")
                st.dataframe(df_train.head())

                # Forecast (необязательно)
                if forecast_file:
                    ext_fc = os.path.splitext(forecast_file.name)[1].lower()
                    if ext_fc == ".csv":
                        df_fore = pd.read_csv(forecast_file)
                    else:
                        df_fore = pd.read_excel(forecast_file)
                    st.session_state["df_forecast"] = df_fore
                    st.success("FORECAST-файл загружен!")
                    st.write("**Forecast (первые строки):**")
                    st.dataframe(df_fore.head())
                else:
                    st.session_state["df_forecast"] = None
                    st.info("Файл forecast не загружен, будем прогнозировать на train.")

            except Exception as e:
                st.error(f"Ошибка при загрузке: {e}")
                logging.error(str(e))

    # --------- 2. Настройки столбцов (дата, target, id) ---------
    st.sidebar.header("2. Настройки столбцов")
    if "df" in st.session_state and st.session_state["df"] is not None:
        columns_available = list(st.session_state["df"].columns)
    else:
        columns_available = []

    dt_col = st.sidebar.selectbox("Колонка даты/времени", ["<нет>"]+columns_available)
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"]+columns_available)
    id_col = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"]+columns_available)

    # До 3 статических
    st.sidebar.header("Статические признаки (до 3)")
    possible_static = [c for c in columns_available if c not in [dt_col,tgt_col,id_col,"<нет>"]]
    static_feats = st.sidebar.multiselect("Выберите статические поля", possible_static, default=[])

    # Чекбокс праздников
    use_holidays = st.sidebar.checkbox("Учитывать праздники России?", value=False)

    # --------- 3. Заполнение пропусков ---------
    st.sidebar.header("3. Обработка пропусков")
    fill_method = st.sidebar.selectbox(
        "Способ заполнения пропусков",
        ["None", "Constant=0", "Group mean", "Forward fill"]
    )
    # Выбор: какие поля использовать для group-mean. Предположим, это подмножество статических
    group_cols_for_fill = []
    if fill_method in ["Group mean", "Forward fill"]:
        # Предположим, у пользователя есть пара-тройка статиков, мы предлагаем
        group_cols_for_fill = st.sidebar.multiselect(
            "Колонки для группировки (например, магазин, страна)",
            static_feats, 
            default=static_feats[:2]  # возьмём 2 по умолчанию
        )

    # --------- 4. Метрика ----------
    st.sidebar.header("4. Метрика")
    metrics_list = list(METRICS_DICT.keys())
    def_metric_idx = metrics_list.index("MASE (Mean absolute scaled error)") if "MASE (Mean absolute scaled error)" in metrics_list else 0
    chosen_metric = st.sidebar.selectbox("Метрика", metrics_list, index=def_metric_idx)
    st.sidebar.write(f"Описание: {METRICS_DICT[chosen_metric]}")

    # --------- 5. Выбор моделей ----------
    st.sidebar.header("5. Модели")
    all_models_opt = "* (все)"
    model_keys = list(AG_MODELS.keys())
    model_choices = [all_models_opt] + model_keys
    chosen_models = st.sidebar.multiselect(
        "Какие модели",
        model_choices,
        default=[all_models_opt]
    )

    # --------- 6. Пресет, time_limit, quantile vs mean ----------
    st.sidebar.header("6. Пресет и прочее")
    presets = st.sidebar.selectbox("Presets", ["fast_quality", "medium_quality", "high_quality", "best_quality"], index=1)
    prediction_length = st.sidebar.number_input("Длина прогноза", min_value=1, max_value=365, value=30)
    time_limit = st.sidebar.number_input("time_limit (сек)", min_value=10, max_value=36000, value=60)
    
    # Чекбокс mean only
    mean_forecast_only = st.sidebar.checkbox("Прогнозить только среднее (mean)?", value=False)

    # --------- 7. Категориальные (графики) ----------
    st.sidebar.header("7. Категориальные (графики)")
    cat_mode = st.sidebar.selectbox("Режим", ["Игнорировать категории", "Прогноз по категориям"])
    max_graphs = st.sidebar.number_input("Сколько топ-графиков (N)", min_value=1, max_value=10, value=5)

    # -------- Состояния (predictor, preds, etc.) --------
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None

    # --------- Кнопка: Обучить модель ---------
    st.sidebar.header("Обучение модели")
    if st.sidebar.button("Обучить модель"):
        df_train = st.session_state.get("df")
        if df_train is None:
            st.warning("Сначала загрузите TRAIN-файл.")
        else:
            if dt_col=="<нет>" or tgt_col=="<нет>" or id_col=="<нет>":
                st.error("Не выбраны все ключевые столбцы (дата, target, id).")
            else:
                try:
                    df_train2 = df_train.copy()

                    # (1) Преобразуем дату, если нужно
                    if not pd.api.types.is_datetime64_any_dtype(df_train2[dt_col]):
                        df_train2[dt_col] = pd.to_datetime(df_train2[dt_col], errors="coerce")

                    # (2) Если чекбокс праздников
                    if use_holidays:
                        df_train2 = add_russian_holiday_feature(df_train2, date_col=dt_col, holiday_col="russian_holiday")

                    # (3) Заполнение пропусков
                    df_train2 = fill_missing_values(df_train2, method=fill_method, group_cols=group_cols_for_fill)

                    # (4) Формируем static_df (если выбрано)
                    static_df = None
                    if static_feats:
                        tmp = df_train2[[id_col]+static_feats].drop_duplicates(subset=[id_col])
                        tmp = tmp.rename(columns={id_col:"item_id"}).set_index("item_id", drop=False)
                        static_df = tmp.drop(columns=["item_id"], errors="ignore")

                    # (5) convert_to_timeseries
                    df_prepared = convert_to_timeseries(
                        df_train2,
                        id_col, dt_col, tgt_col,
                        static_df=static_df
                    )
                    ts_df = make_timeseries_dataframe(df_prepared)
                    
                    # (6) Формируем hyperparameters
                    if (len(chosen_models)==1 and chosen_models[0]==all_models_opt) or len(chosen_models)==0:
                        hyperparams = None
                    else:
                        no_star = [m for m in chosen_models if m!=all_models_opt]
                        hyperparams = {m:{} for m in no_star}

                    # (7) Метрика
                    eval_key = chosen_metric.split(" ")[0]

                    # (8) quantile_levels
                    from autogluon.timeseries import TimeSeriesPredictor
                    q_levels = None
                    if mean_forecast_only:
                        q_levels = [0.5]

                    predictor = TimeSeriesPredictor(
                        target="target",
                        prediction_length=prediction_length,
                        eval_metric=eval_key,
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

                    # Лидерборд
                    lb = predictor.leaderboard(ts_df)
                    st.session_state["leaderboard"] = lb
                    st.subheader("Лидерборд")
                    st.dataframe(lb)

                    # fit_summary
                    summary = predictor.fit_summary()
                    st.session_state["fit_summary"] = summary

                    best_model = lb.iloc[0]["model"]
                    best_score = lb.iloc[0]["score_val"]
                    st.info(f"**Лучшая модель**: {best_model}  (score_val={best_score})")

                    with st.expander("fit_summary (подробности)"):
                        st.text(summary)

                except Exception as ex:
                    st.error(f"Ошибка обучения: {ex}")
                    logging.error(str(ex))

    # -------- Прогноз --------
    st.sidebar.header("Прогноз")
    if st.sidebar.button("Сделать прогноз"):
        predictor = st.session_state.get("predictor")
        if predictor is None:
            st.warning("Модель не обучена.")
        else:
            df_train = st.session_state.get("df")
            df_fore = st.session_state.get("df_forecast")
            if df_train is None:
                st.error("Нет train-данных.")
            else:
                try:
                    # Выбираем df, на котором хотим прогнозировать
                    # Если df_fore not None -> прогноз на forecast
                    # Иначе -> train
                    if df_fore is not None:
                        st.subheader("Прогноз на FORECAST-файле")
                        df_pred = df_fore.copy()
                    else:
                        st.subheader("Прогноз на TRAIN (т.к. forecast не загружен)")
                        df_pred = df_train.copy()

                    # Обработка пропусков/праздников так же, как при train
                    if not pd.api.types.is_datetime64_any_dtype(df_pred[dt_col]):
                        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")

                    if use_holidays:
                        df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")

                    df_pred = fill_missing_values(df_pred, method=fill_method, group_cols=group_cols_for_fill)

                    static_df = None
                    if static_feats:
                        tmp = df_pred[[id_col]+static_feats].drop_duplicates(subset=[id_col])
                        tmp = tmp.rename(columns={id_col:"item_id"}).set_index("item_id", drop=False)
                        static_df = tmp.drop(columns=["item_id"], errors="ignore")

                    # Если target_col нет, создаём
                    if tgt_col not in df_pred.columns:
                        df_pred[tgt_col] = None

                    df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col, static_df=static_df)
                    ts_df = make_timeseries_dataframe(df_prepared)

                    preds = forecast(predictor, ts_df)
                    st.session_state["predictions"] = preds

                    preds_df = preds.reset_index()
                    st.dataframe(preds_df.head())

                    # Рисуем
                    if "0.5" in preds_df.columns:
                        if cat_mode=="Прогноз по категориям":
                            item_sums = preds_df.groupby("item_id")["0.5"].sum().sort_values(ascending=False)
                            top_items = item_sums.index[:max_graphs]
                            for it in top_items:
                                subset = preds_df[preds_df["item_id"]==it]
                                fig_ = px.line(subset, x="timestamp", y="0.5", title=f"Прогноз (медиана) для {it}")
                                st.plotly_chart(fig_, use_container_width=True)
                        else:
                            fig_ = px.line(preds_df, x="timestamp", y="0.5", color="item_id",
                                           title="Общий прогноз (медиана 0.5)")
                            st.plotly_chart(fig_, use_container_width=True)
                    else:
                        st.warning("Нет колонки '0.5' в прогнозе (для квантильной модели).")

                except Exception as ex:
                    st.error(f"Ошибка при прогнозировании: {ex}")
                    logging.error(str(ex))

    # -------- Сохранение --------
    st.sidebar.header("Сохранение/логи")
    save_path = st.sidebar.text_input("Путь (Excel)", "results.xlsx")
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
            st.success("Модель загружена!")
        except Exception as e:
            st.error(f"Ошибка: {e}")

    if st.sidebar.button("Показать логи"):
        logs = read_logs()
        st.subheader("Логи")
        st.text(logs)


if __name__=="__main__":
    main()



