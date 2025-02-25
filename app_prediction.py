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
    tgt_cols = st.session_state.get("tgt_cols_key", [])  # Список целевых переменных
    id_col = st.session_state.get("id_col_key")
    
    # Проверяем, используется ли режим множественного выбора целевых переменных
    use_multi_target = st.session_state.get("use_multi_target_key", False)

    # Проверяем наличие необходимых данных в соответствии с режимом
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
                if st.session_state.get("use_holidays_key", False):
                    df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")
                
                # Заполняем пропуски
                df_pred = fill_missing_values(
                    df_pred,
                    st.session_state.get("fill_method_key", "None"),
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
                    freq_short = freq_val.split(" ")[0]
                    ts_df = ts_df.convert_frequency(freq_short)
                    ts_df = ts_df.fill_missing_values(method="ffill")
                
                # Прогнозирование для текущей целевой переменной
                status_text.text(f"Выполнение прогнозирования для {tgt_col}...")
                preds = forecast(predictor, ts_df)
                
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
                
                # Сохраняем данные графиков в session_state
                if "graphs_data" not in st.session_state:
                    st.session_state["graphs_data"] = {}
                
                st.session_state["graphs_data"]["preds_df"] = preds_df
                st.session_state["graphs_data"]["unique_ids"] = unique_ids
                
                # Интерактивная визуализация
                st.subheader("Графики прогноза (0.5)")
                
                # Настройки визуализации с ключами
                max_graphs = st.slider("Максимальное количество графиков", 
                                    1, min(10, len(unique_ids)), 3, 
                                    key="max_graphs_slider")
                
                # Выбор ID для визуализации с ключом
                selected_ids = st.multiselect(
                    "Выберите ID для визуализации", 
                    options=unique_ids,
                    default=unique_ids[:min(3, len(unique_ids))],
                    key="selected_ids_multiselect"
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



