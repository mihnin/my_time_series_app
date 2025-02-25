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
from src.utils.exporter import generate_excel_buffer  # Добавлен новый импорт

# Заменить существующий декоратор в начале файла (примерно строка 13)
@st.cache_data(ttl=3600)  # Кэш действителен 1 час
def get_cached_predictions(predictions_data):
    """Кэширует только результаты прогнозирования"""
    return predictions_data

def run_prediction():
    """Функция для запуска прогнозирования."""
    # Получаем все необходимые значения из session_state в начале функции
    predictor = st.session_state.get("predictor")
    dt_col = st.session_state.get("dt_col_key")
    tgt_cols = st.session_state.get("tgt_cols_key", [])
    id_col = st.session_state.get("id_col_key")
    use_multi_target = st.session_state.get("use_multi_target_key", False)
    use_holidays = st.session_state.get("use_holidays_key", False)
    fill_method = st.session_state.get("fill_method_key", "None")
    group_cols_for_fill = st.session_state.get("group_cols_for_fill_key", [])
    freq_val = st.session_state.get("freq_key", "auto (угадать)")
    static_feats_val = st.session_state.get("static_feats_key", [])

    if predictor is None:
        st.warning("Сначала обучите модель или загрузите уже существующую!")
        return False

    # Проверяем, используется ли режим множественного выбора целевых переменных
    if dt_col == "<нет>":
        st.error("Колонка с датой должна быть указана!")
        return False
    
    if use_multi_target:
        if not tgt_cols:
            st.error("Выберите хотя бы одну целевую переменную!")
            return False
        active_tgt_cols = tgt_cols
    else:
        tgt_col = st.session_state.get("tgt_col_key")
        if tgt_col == "<нет>":
            st.error("Выберите целевую переменную!")
            return False
        active_tgt_cols = [tgt_col]

    active_tgt_cols = [tgt_col]

    # Добавить эту проверку
    if not active_tgt_cols:
        st.error("Список целевых переменных пуст!")
        return False

    df_train = st.session_state.get("df")
    if df_train is None:
        st.error("Нет train данных!")
        return False

    try:
        # Добавляем индикатор прогресса
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Проверяем, нужно ли обрабатывать данные как множество временных рядов без ID
        if id_col == "<нет>" and len(active_tgt_cols) > 0:
            st.subheader("Множественное прогнозирование целевых переменных")
            status_text.text("Подготовка данных для множественного прогнозирования...")
            
            all_predictions = []
            
            for i, tgt_col in enumerate(active_tgt_cols):
                status_text.text(f"Обработка {tgt_col} ({i+1}/{len(active_tgt_cols)})...")
                progress_bar.progress(int(10 + (i / len(active_tgt_cols) * 40)))
                
                # Создаем копию с необходимыми колонками
                df_pred = df_train[[dt_col, tgt_col]].copy()
                df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")
                
                # Создаем искусственный ID из названия колонки
                artificial_id = f"col_{tgt_col}"
                
                # Добавляем признаки при необходимости
                if use_holidays:
                    df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")
                
                # Заполняем пропуски используя локальные переменные
                df_pred = fill_missing_values(
                    df_pred,
                    fill_method,
                    []  # Нет группировки для одной переменной
                )
                
                # Подготовка для TimeSeriesDataFrame
                df_pred_long = pd.DataFrame({
                    'item_id': [artificial_id] * len(df_pred),
                    'timestamp': df_pred[dt_col],
                    'target': df_pred[tgt_col]
                })
                
                # Частота (если указана явно)
                freq_val = st.session_state.get("freq_key", "auto (угадать)")
                
                # Преобразуем в TimeSeriesDataFrame
                ts_df = make_timeseries_dataframe(df_pred_long)
                
                # Устанавливаем частоту, если она задана явно
                if freq_val != "auto (угадать)":
                    freq_short = freq_val.split(" ")[0] if " " in freq_val else freq_val
                    ts_df = ts_df.convert_frequency(freq_short)
                    ts_df = ts_df.fill_missing_values(method="ffill")
                
                # Прогнозирование для текущей целевой переменной
                status_text.text(f"Выполнение прогнозирования для {tgt_col}...")
                preds = forecast(predictor, ts_df)
                preds = get_cached_predictions(preds)
                
                # Добавляем имя исходной переменной в прогноз
                preds["original_variable"] = tgt_col
                all_predictions.append(preds)
            
            # Объединяем все прогнозы
            if all_predictions:
                combined_preds = pd.concat(all_predictions)
                st.session_state["predictions"] = combined_preds
                
                # Отображаем результаты
                st.subheader("Предсказанные значения (первые строки каждой переменной)")
                
                # Показываем по несколько строк для каждой переменной
                samples = []
                for var in active_tgt_cols:
                    var_preds = combined_preds[combined_preds["original_variable"] == var]
                    if not var_preds.empty:
                        samples.append(var_preds.head(3))
                
                if samples:
                    sample_df = pd.concat(samples).reset_index()
                    st.dataframe(sample_df)
                
                # Визуализация результатов для каждой переменной
                st.subheader("Графики прогнозов")
                
                # Настройки визуализации
                max_graphs = st.slider("Максимальное количество графиков", 1, len(active_tgt_cols), min(5, len(active_tgt_cols)))
                
                # Выбор переменных для визуализации
                selected_vars = st.multiselect(
                    "Выберите переменные для визуализации", 
                    options=active_tgt_cols,
                    default=active_tgt_cols[:min(3, len(active_tgt_cols))]
                )
                
                # Создаем графики для выбранных переменных
                for i, var in enumerate(selected_vars[:max_graphs]):
                    var_preds = combined_preds[combined_preds["original_variable"] == var].reset_index()
                    
                    if "0.5" in var_preds.columns:
                        fig = px.line(
                            var_preds, x="timestamp", y="0.5",
                            title=f"Прогноз для {var} (квантиль 0.5)",
                            labels={"0.5": f"Прогноз {var}", "timestamp": "Дата"},
                            markers=True
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Сводный график всех переменных
                if st.checkbox("Показать сводный график всех переменных"):
                    combined_view = []
                    
                    for var in active_tgt_cols:
                        var_preds = combined_preds[combined_preds["original_variable"] == var].reset_index()
                        if "0.5" in var_preds.columns and not var_preds.empty:
                            var_preds["variable"] = var
                            var_preds = var_preds.rename(columns={"0.5": "prediction"})
                            combined_view.append(var_preds[["timestamp", "prediction", "variable"]])
                    
                    if combined_view:
                        all_vars_df = pd.concat(combined_view)
                        fig_all = px.line(
                            all_vars_df, x="timestamp", y="prediction", color="variable",
                            title="Сводный прогноз всех переменных",
                            labels={"prediction": "Прогнозное значение", "timestamp": "Дата"},
                            markers=True
                        )
                        st.plotly_chart(fig_all, use_container_width=True)
                
                progress_bar.progress(100)
                status_text.text("Множественное прогнозирование успешно завершено!")
                
                # Показываем использование памяти
                process = psutil.Process(os.getpid())
                memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
                st.info(f"Текущее использование памяти: {memory_usage:.2f} МБ")
                
                return True
            
            else:
                st.error("Не удалось получить прогнозы ни для одной переменной")
                return False
                
        else:
            # Оригинальная логика для стандартного случая с одной целевой переменной и ID
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

            tgt_col = active_tgt_cols[0]  # Берем первую (единственную) целевую переменную
            if tgt_col not in df_pred.columns:
                df_pred[tgt_col] = None

            status_text.text("Преобразование в TimeSeriesDataFrame...")
            df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col)
            ts_df = make_timeseries_dataframe(df_prepared, static_df=static_df)
            progress_bar.progress(50)

            freq_val = st.session_state.get("freq_key", "auto (угадать)")
            if freq_val != "auto (угадать)":
                status_text.text(f"Преобразование к частоте {freq_val}...")
                freq_short = freq_val.split(" ")[0] if " " in freq_val else freq_val
                ts_df = ts_df.convert_frequency(freq_short)
                ts_df = ts_df.fill_missing_values(method="ffill")
            progress_bar.progress(60)

            # Начальное время
            start_time = time.time()

            # Проверяем, изменились ли входные данные или нет прогноза
            prediction_needed = True

            if "last_prediction_inputs" in st.session_state:
                last_ts_df_str = st.session_state["last_prediction_inputs"].get("ts_df_str")
                current_ts_df_str = str(ts_df.head())
                
                # Если входные данные не изменились и прогноз уже есть
                if last_ts_df_str == current_ts_df_str and "predictions" in st.session_state:
                    preds = st.session_state["predictions"]
                    prediction_needed = False
                    status_text.text("Используем существующий прогноз...")

            if prediction_needed:
                # Измеряем начальное использование памяти
                start_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                
                status_text.text("Выполнение прогнозирования...")
                preds = forecast(predictor, ts_df)
                
                # Измеряем конечное использование памяти
                end_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
                st.info(f"Использовано памяти при прогнозировании: {end_mem - start_mem:.2f} МБ")
                
                # Сохраняем входные данные для следующей проверки
                if "last_prediction_inputs" not in st.session_state:
                    st.session_state["last_prediction_inputs"] = {}
                st.session_state["last_prediction_inputs"]["ts_df_str"] = str(ts_df.head())
                st.session_state["predictions"] = preds
            
            # Обновляем прогресс
            elapsed_time = time.time() - start_time
            status_text.text(f"Прогнозирование завершено за {elapsed_time:.2f} секунд!")
            progress_bar.progress(80)
            
            st.session_state["predictions"] = preds

            st.subheader("Предсказанные значения (первые строки)")
            st.dataframe(preds.reset_index().head())

            progress_bar.progress(100)
            status_text.text("Прогнозирование успешно завершено!")

            # Сразу предложим пользователю скачать результаты
            if not st.session_state.get("train_predict_save_checkbox", False):
                excel_buffer = generate_excel_buffer(preds, st.session_state.get("leaderboard"), 
                                                    st.session_state.get("static_df_train"), 
                                                    st.session_state.get("weighted_ensemble_info"))
                
                st.download_button(
                    label="📥 Скачать результаты в Excel",
                    data=excel_buffer.getvalue(),
                    file_name="forecast_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # Освобождаем память
            gc.collect()

            return True

    except Exception as ex:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Ошибка прогноза: {ex}")
        st.expander("Детали ошибки").code(error_details)
        # Логирование ошибки
        import logging
        logging.error(f"Ошибка прогноза: {ex}")
        gc.collect()  # Освобождаем память при ошибке
        return False



