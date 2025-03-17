# app_prediction.py
import streamlit as st
import pandas as pd
import plotly.express as px
import time
import gc
import psutil
import os
import logging

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe, forecast
from src.features.drift_detection import detect_concept_drift, display_drift_results
from src.utils.exporter import generate_excel_buffer
from app_ui import get_base_freq

# Заменить существующий декоратор в начале файла
@st.cache_data(ttl=3600)  # Кэш действителен 1 час
def get_cached_predictions(predictions_data):
    """Кэширует только результаты прогнозирования"""
    return predictions_data

# Фактическая реализация предсказания
def _execute_prediction(predictor, dt_col, tgt_col, id_col, df_forecast=None, use_multi_target=False, 
                      use_holidays=False, fill_method="None", group_cols_for_fill=None, 
                      freq=None, static_feats=None, horizon_val=10, **kwargs):
    """Выполняет предсказание с переданными параметрами"""
    try:
        # Инициализируем значения по умолчанию
        if static_feats is None:
            static_feats = []
        if group_cols_for_fill is None:
            group_cols_for_fill = []
            
        # Используем данные из сессии, если не указаны явно
        if df_forecast is None:
            df_forecast = st.session_state.get("df")
            
        # Проверка наличия предиктора
        if predictor is None:
            return {
                'success': False,
                'error': 'Предиктор не найден. Сначала обучите модель или загрузите существующую.'
            }
        
        # Проверка наличия данных для прогноза
        if df_forecast is None:
            return {
                'success': False,
                'error': 'Нет данных для прогноза. Загрузите файл с данными для предсказания.'
            }
        
        # Логируем начало процесса предсказания
        logging.info(f"Начало выполнения предсказания")
        logging.info(f"Параметры предсказания: dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}, "
                    f"use_multi_target={use_multi_target}, horizon={horizon_val}")
        
        # Определяем активные целевые колонки
        if use_multi_target:
            active_tgt_cols = kwargs.get('tgt_cols', [])
            if not active_tgt_cols:
                return {
                    'success': False,
                    'error': 'Выберите хотя бы одну целевую переменную!'
                }
        else:
            active_tgt_cols = [tgt_col]
            if active_tgt_cols[0] == "<нет>":
                return {
                    'success': False,
                    'error': 'Выберите целевую переменную!'
                }
        
        logging.info(f"Активные целевые колонки: {active_tgt_cols}")
        
        # Подготовка данных для прогноза
        df_with_features = df_forecast.copy()
        
        # Добавляем признак с праздниками если нужно
        if use_holidays:
            df_with_features = add_russian_holiday_feature(df_with_features, dt_col)
            logging.info("Добавлен признак с российскими праздниками")
        
        # Заполняем пропуски, если нужно
        if fill_method != "None":
            logging.info(f"Заполнение пропусков методом {fill_method}")
            df_with_features = fill_missing_values(df_with_features, method=fill_method, group_cols=group_cols_for_fill)
        
        # Результаты для всех целевых переменных
        all_forecasts = {}
        all_graphs_data = {}
        
        start_time = time.time()
        
        # Для каждой целевой переменной делаем отдельный прогноз
        for target_column in active_tgt_cols:
            # Преобразуем в формат временных рядов
            df_formatted = convert_to_timeseries(
                df_with_features,
                id_col=id_col,
                timestamp_col=dt_col,
                target_col=target_column
            )
            
            # Получаем или создаем статические признаки, если они есть
            static_df = None
            if static_feats and len(static_feats) > 0:
                # Выделяем статические признаки в отдельный DataFrame
                logging.info(f"Используются статические признаки: {static_feats}")
                static_cols = [col for col in df_with_features.columns if col in static_feats]
                if static_cols:
                    static_df = df_with_features[[id_col] + static_cols].drop_duplicates(id_col).copy()
                    static_df.rename(columns={id_col: "item_id"}, inplace=True)
                    static_df.set_index("item_id", inplace=True)
                    logging.info(f"Создан DataFrame статических признаков с колонками: {list(static_df.columns)}")
            
            # Создаем TimeSeriesDataFrame
            ts_df = make_timeseries_dataframe(df_formatted, static_df)
            
            # Устанавливаем частоту, если нужно
            actual_freq = getattr(predictor, 'freq', 'D')
            if freq and freq != "auto":
                try:
                    logging.info(f"Устанавливаем явную частоту данных: {freq}")
                    ts_df = ts_df.convert_frequency(freq=freq)
                    actual_freq = freq
                except Exception as e:
                    logging.error(f"Ошибка при установке частоты: {str(e)}")
            
            logging.info(f"Прогнозирование для колонки {target_column}, частота: {actual_freq}")
            
            # Делаем прогноз
            try:
                forecast_result = predictor.predict(ts_df)
                logging.info(f"Прогноз для {target_column} успешно выполнен")
            except Exception as e:
                logging.error(f"Ошибка при выполнении прогноза для {target_column}: {str(e)}")
                continue
            
            # Проверяем наличие дрейфа концепции
            try:
                # В текущей версии AutoGluon TimeSeriesPredictor не хранит train_data напрямую
                # Отключаем проверку дрейфа концепции
                logging.info(f"Проверка дрейфа концепции отключена")
                drift_detected = False
                drift_info = {"message": "Проверка дрейфа отключена, модель не хранит тренировочные данные"}
            except Exception as e:
                logging.error(f"Ошибка при проверке дрейфа концепции: {str(e)}")
                drift_detected = False
                drift_info = {"error": str(e)}
            
            # Сохраняем результаты
            all_forecasts[target_column] = {
                'predictions': forecast_result,
                'drift_detected': drift_detected,
                'drift_info': drift_info
            }
            
            # Подготавливаем данные для графиков
            graphs_data = {}
            
            try:
                # Получаем список уникальных идентификаторов из исходных данных
                unique_ids = df_formatted["item_id"].unique()
                
                # Проверяем структуру результата прогноза
                forecast_columns = forecast_result.columns.tolist()
                logging.info(f"Колонки в результатах прогноза: {forecast_columns}")
                
                for item_id in unique_ids:
                    # Получаем исторические данные для текущего ID
                    item_data = df_formatted[df_formatted["item_id"] == item_id]
                    
                    # Проверяем наличие колонки 'item_id' в результатах прогноза
                    if 'item_id' in forecast_result.index.names:
                        # Если item_id в мультииндексе, получаем данные по нему
                        try:
                            item_forecast = forecast_result.xs(item_id, level='item_id')
                            has_forecast = True
                        except KeyError:
                            logging.warning(f"ID {item_id} отсутствует в результатах прогноза")
                            has_forecast = False
                    elif isinstance(forecast_result.index, pd.MultiIndex) and len(forecast_result.index.names) > 1:
                        # Предполагаем, что первый уровень индекса - это item_id
                        try:
                            item_forecast = forecast_result.xs(item_id, level=0)
                            has_forecast = True
                        except KeyError:
                            logging.warning(f"ID {item_id} отсутствует в результатах прогноза")
                            has_forecast = False
                    else:
                        # Если структура прогноза другая, берем весь прогноз для отображения
                        logging.warning(f"Структура прогноза не содержит item_id, использую все результаты")
                        item_forecast = forecast_result
                        has_forecast = True
                    
                    if has_forecast and not item_forecast.empty:
                        # Объединяем исторические данные и прогноз для графика
                        historical = item_data.reset_index()[["timestamp", "target"]].rename(
                            columns={"timestamp": "date", "target": "value"}
                        )
                        historical["type"] = "Исторические"
                        
                        # Подготавливаем данные прогноза
                        forecast_df = item_forecast.reset_index()
                        
                        # Определяем колонки для значений и дат в прогнозе
                        date_col = "timestamp" if "timestamp" in forecast_df.columns else forecast_df.columns[0]
                        # Используем медианный прогноз (0.5 квантиль) или первую числовую колонку
                        value_cols = [col for col in forecast_df.columns if col not in [date_col, 'item_id'] and pd.api.types.is_numeric_dtype(forecast_df[col])]
                        value_col = "0.5" if "0.5" in value_cols else (value_cols[0] if value_cols else None)
                        
                        if value_col:
                            forecast_plot = forecast_df[[date_col, value_col]].rename(
                                columns={date_col: "date", value_col: "value"}
                            )
                            forecast_plot["type"] = "Прогноз"
                            
                            # Создаем датафрейм для графика
                            plot_df = pd.concat([historical, forecast_plot], ignore_index=True)
                            
                            # Добавляем интервалы если они есть
                            if "0.1" in value_cols and "0.9" in value_cols:
                                forecast_lower = forecast_df[[date_col, "0.1"]].rename(
                                    columns={date_col: "date", "0.1": "lower"}
                                )
                                forecast_upper = forecast_df[[date_col, "0.9"]].rename(
                                    columns={date_col: "date", "0.9": "upper"}
                                )
                                # Соединяем с основным датафреймом
                                plot_df = pd.merge(plot_df, forecast_lower, on="date", how="left")
                                plot_df = pd.merge(plot_df, forecast_upper, on="date", how="left")
                            
                            # Сохраняем данные для графика
                            graphs_data[item_id] = plot_df
                        else:
                            logging.warning(f"Не удалось найти колонку со значением прогноза для ID {item_id}")
                    else:
                        logging.warning(f"Прогнозов для ID {item_id} не получено")
                
                # Сохраняем данные для графиков для текущей целевой переменной
                all_graphs_data[target_column] = graphs_data
                
            except Exception as e:
                logging.error(f"Ошибка при подготовке данных для графиков: {str(e)}")
                all_graphs_data[target_column] = {}
        
        # Проверяем успешность выполнения
        if all_forecasts:
            logging.info(f"Прогнозирование успешно завершено за {time.time() - start_time:.2f} сек.")
            return {
                'success': True,
                'forecasts': all_forecasts,
                'graphs_data': all_graphs_data
            }
        else:
            return {
                'success': False,
                'error': 'Не удалось сделать прогноз ни для одной колонки.'
            }
    
    except Exception as e:
        logging.exception(f"Ошибка при выполнении прогноза: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def run_prediction():
    """Запускает процесс прогнозирования"""
    try:
        # Получаем значения из session_state
        predictor = st.session_state.get("predictor")
        dt_col = st.session_state.get("dt_col_key")
        tgt_col = st.session_state.get("tgt_col_key")
        id_col = st.session_state.get("id_col_key")
        use_holidays = st.session_state.get("use_holidays_key", False)
        fill_method = st.session_state.get("fill_method_key", "None")
        group_cols_for_fill = st.session_state.get("group_cols_for_fill_key", [])
        freq = st.session_state.get("freq_key")
        static_feats = st.session_state.get("static_feats_key", [])
        horizon_val = st.session_state.get("prediction_length_key", 10)
        
        # Логируем начало процесса
        logging.info(f"Запуск прогнозирования с параметрами: dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}")
        
        # Извлекаем базовую частоту из пользовательского выбора
        base_freq = get_base_freq(freq)
        
        # Проверяем наличие предиктора
        if predictor is None:
            st.error("Сначала обучите модель или загрузите существующую")
            return
        
        # Прогресс-бар и текстовый статус
        progress_text = "Выполнение прогноза..."
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text(progress_text)
        
        # Запускаем прогнозирование
        with st.spinner("Прогнозирование..."):
            # Вызываем функцию напрямую
            prediction_params = {
                "predictor": predictor,
                "dt_col": dt_col,
                "tgt_col": tgt_col,
                "id_col": id_col,
                "use_holidays": use_holidays,
                "fill_method": fill_method,
                "group_cols_for_fill": group_cols_for_fill,
                "freq": base_freq,
                "static_feats": static_feats,
                "horizon_val": horizon_val
            }
            
            # Обновляем прогресс
            progress_bar.progress(20)
            status_text.text("Подготовка данных...")
            
            # Выполняем прогнозирование
            result = _execute_prediction(**prediction_params)
            
            # Обновляем прогресс
            progress_bar.progress(80)
            status_text.text("Формирование результатов...")
            
            # Обрабатываем результат
            if result.get('success'):
                # Сохраняем результаты в session_state
                st.session_state["predictions"] = result.get('forecasts')
                st.session_state["graphs_data"] = result.get('graphs_data')
                st.session_state["df_forecast"] = get_cached_predictions(result)
                
                # Отображаем результаты
                progress_bar.progress(100)
                status_text.text("Прогноз выполнен!")
                st.success("✅ Прогнозирование успешно завершено!")
                
                # Визуализируем прогнозы
                for target_col, graphs_data in result.get('graphs_data', {}).items():
                    # Если данных для визуализации нет, пропускаем
                    if not graphs_data:
                        st.warning(f"Нет данных для визуализации прогноза для {target_col}")
                        continue
                    
                    st.subheader(f"Визуализация прогноза для колонки: {target_col}")
                    
                    # Отображаем графики для каждого ID
                    for item_id, plot_df in graphs_data.items():
                        if plot_df.empty:
                            continue
                        
                        # Проверяем наличие интервалов
                        has_intervals = 'lower' in plot_df.columns and 'upper' in plot_df.columns
                        
                        # Создаем график
                        fig = px.line(plot_df, x="date", y="value", color="type", 
                                     title=f"Прогноз для ID: {item_id}",
                                     labels={"value": target_col, "date": "Дата", "type": "Тип данных"})
                        
                        # Добавляем интервалы если они есть
                        if has_intervals:
                            forecast_only = plot_df[plot_df["type"] == "Прогноз"].copy()
                            fig.add_scatter(x=forecast_only["date"], y=forecast_only["lower"], 
                                           mode='lines', line=dict(width=0), 
                                           showlegend=False)
                            fig.add_scatter(x=forecast_only["date"], y=forecast_only["upper"], 
                                           mode='lines', line=dict(width=0), 
                                           fill='tonexty', fillcolor='rgba(0, 176, 246, 0.2)', 
                                           name='90% интервал')
                        
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                
                # Кнопка для сохранения результатов в Excel
                excel_buffer = generate_excel_buffer(result)
                if excel_buffer:
                    st.download_button(
                        label="📥 Скачать результаты прогноза в Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"forecast_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    
                # Если включен чекбокс "Обучение, Прогноз и Сохранение", автоматически сохраняем результаты
                if st.session_state.get('train_predict_save_checkbox', False):
                    st.info("🔄 Сохранение результатов...")
                    # Логика для автоматического сохранения результатов
                    # ...
            else:
                # Задача завершилась с ошибкой
                progress_bar.progress(100)
                status_text.text("Ошибка при выполнении прогноза!")
                st.error(f"❌ Ошибка при выполнении прогноза: {result.get('error', 'Неизвестная ошибка')}")
    
    except Exception as e:
        st.error(f"❌ Произошла ошибка при прогнозировании: {str(e)}")
        logging.exception(f"Ошибка при прогнозировании: {e}")
        return 