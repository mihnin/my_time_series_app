# app_prediction.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import gc
import psutil
import os

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe, forecast
from src.features.drift_detection import detect_concept_drift, display_drift_results

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

    df_train = st.session_state.get("df")
    if df_train is None:
        st.error("Нет train данных!")
        return False

    try:
        # Добавляем индикатор прогресса
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        st.subheader("Прогноз на TRAIN")
        status_text.text("Подготовка данных для прогнозирования...")
        df_pred = df_train.copy()
        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")
        progress_bar.progress(10)

        if st.session_state.get("use_holidays_key", False):
            status_text.text("Добавление признака праздников...")
            df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")
            st.info("Признак `russian_holiday` включён при прогнозировании.")
        progress_bar.progress(20)

        status_text.text("Заполнение пропусков...")
        df_pred = fill_missing_values(
            df_pred,
            st.session_state.get("fill_method_key", "None"),
            st.session_state.get("group_cols_for_fill_key", [])
        )
        progress_bar.progress(30)

        st.session_state["df"] = df_pred

        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            status_text.text("Подготовка статических признаков...")
            tmp = df_pred[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col: "item_id"}, inplace=True)
            static_df = tmp
        progress_bar.progress(40)

        if tgt_col not in df_pred.columns:
            df_pred[tgt_col] = None

        status_text.text("Преобразование в TimeSeriesDataFrame...")
        df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_prepared, static_df=static_df)
        progress_bar.progress(50)

        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        if freq_val != "auto (угадать)":
            status_text.text(f"Преобразование к частоте {freq_val}...")
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
        progress_bar.progress(60)

        # Начальное время
        start_time = time.time()
        status_text.text("Выполнение прогнозирования...")
        
        # Запускаем прогнозирование
        preds = forecast(predictor, ts_df)
        
        # Обновляем прогресс
        elapsed_time = time.time() - start_time
        status_text.text(f"Прогнозирование завершено за {elapsed_time:.2f} секунд!")
        progress_bar.progress(80)
        
        st.session_state["predictions"] = preds

        st.subheader("Предсказанные значения (первые строки)")
        st.dataframe(preds.reset_index().head())
        progress_bar.progress(90)

        # Визуализация результатов
        if "0.5" in preds.columns:
            preds_df = preds.reset_index().rename(columns={"0.5": "prediction"})
            unique_ids = preds_df["item_id"].unique()
            
            # Проверка концепт-дрифта на прогнозе
            if st.checkbox("Проверить концепт-дрифт в прогнозе"):
                with st.spinner("Проверка концепт-дрифта..."):
                    # Подготовка исторических данных
                    historical_df = df_pred.copy()
                    
                    # Подготовка данных прогноза
                    new_df = preds_df.copy()
                    new_df.rename(columns={"timestamp": dt_col, "prediction": tgt_col, "item_id": id_col}, inplace=True)
                    
                    # Обнаружение дрифта
                    drift_results = detect_concept_drift(
                        historical_df, new_df, tgt_col, dt_col, id_col
                    )
                    display_drift_results(drift_results)
            
            # Интерактивная визуализация
            st.subheader("Графики прогноза (0.5)")
            
            # Настройки визуализации
            max_graphs = st.slider("Максимальное количество графиков", 1, min(10, len(unique_ids)), 3)
            
            # Выбор ID для визуализации
            selected_ids = st.multiselect(
                "Выберите ID для визуализации", 
                options=unique_ids,
                default=unique_ids[:min(3, len(unique_ids))]
            )
            
            # Отображение графиков
            for i, uid in enumerate(selected_ids[:max_graphs]):
                subset = preds_df[preds_df["item_id"] == uid]
                fig_ = px.line(
                    subset, x="timestamp", y="prediction",
                    title=f"Прогноз для item_id={uid} (квантиль 0.5)",
                    markers=True
                )
                st.plotly_chart(fig_, use_container_width=True)
            
            # График всех ID
            if st.checkbox("Показать сводный график всех ID"):
                fig_all = px.line(
                    preds_df, x="timestamp", y="prediction", color="item_id",
                    title="Прогноз для всех ID (квантиль 0.5)",
                    markers=True
                )
                st.plotly_chart(fig_all, use_container_width=True)
        else:
            st.info("Колонка '0.5' не найдена — возможно mean_only=True или квантильные настройки отключены.")
        
        progress_bar.progress(100)
        status_text.text("Прогнозирование успешно завершено!")
        
        # Освобождаем память
        gc.collect()
        
        # Показываем использование памяти
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
        st.info(f"Текущее использование памяти: {memory_usage:.2f} МБ")

        return True

    except Exception as ex:
        st.error(f"Ошибка прогноза: {ex}")
        return False



