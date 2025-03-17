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
from src.utils.exporter import generate_excel_buffer  # Добавлен новый импорт
from app_ui import get_base_freq  # Добавляем импорт функции для преобразования частоты

# Новые импорты
from src.utils.queue_manager import get_queue_manager, TaskPriority
from src.utils.session_manager import get_current_session_id, save_to_session
from src.utils.resource_monitor import get_resource_monitor
from src.components.queue_status import show_queue_status

# Заменить существующий декоратор в начале файла (примерно строка 13)
@st.cache_data(ttl=3600)  # Кэш действителен 1 час
def get_cached_predictions(predictions_data):
    """Кэширует только результаты прогнозирования"""
    return predictions_data

# Функция запуска предсказания через очередь
def queue_prediction_task(prediction_params):
    """Добавляет задачу предсказания в очередь"""
    # Получаем текущий ID сессии
    session_id = get_current_session_id()
    
    # Проверяем, можно ли добавить новую задачу (достаточно ли ресурсов)
    resource_monitor = get_resource_monitor()
    if not resource_monitor.can_accept_new_task():
        st.error("Система в данный момент перегружена. Пожалуйста, повторите попытку позже.")
        return None
    
    # Получаем менеджер очереди
    queue_manager = get_queue_manager()
    
    # Добавляем задачу предсказания в очередь с нормальным приоритетом
    task_id = queue_manager.add_task(
        session_id=session_id,
        func=_execute_prediction,
        prediction_params=prediction_params,
        priority=TaskPriority.NORMAL
    )
    
    logging.info(f"Задача предсказания добавлена в очередь, ID: {task_id}")
    
    # Сохраняем ID задачи в сессии для последующего отслеживания
    save_to_session('current_prediction_task_id', task_id)
    
    # Возвращаем ID задачи
    return task_id

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
                # Получаем данные из обученной модели
                train_data = predictor.train_data
                
                drift_detected = False
                drift_info = {}
                
                # Выполняем проверку дрейфа
                if train_data is not None:
                    logging.info(f"Проверка дрейфа концепции для {target_column}")
                    drift_detected, drift_info = detect_concept_drift(
                        historical_df=train_data,
                        new_df=ts_df,
                        target_col='target',
                        date_col='timestamp'
                    )
                    
                    if drift_detected:
                        logging.warning(f"Обнаружен дрейф концепции для {target_column}!")
                else:
                    logging.warning("Невозможно проверить дрейф концепции: нет тренировочных данных в предикторе")
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
            unique_ids = df_formatted["item_id"].unique()
            graphs_data = {}
            
            for item_id in unique_ids:
                item_data = df_formatted[df_formatted["item_id"] == item_id]
                item_forecast = forecast_result[forecast_result["item_id"] == item_id]
                
                if not item_forecast.empty:
                    # Объединяем исторические данные и прогноз для графика
                    historical = item_data.reset_index()[["timestamp", "target"]].rename(
                        columns={"timestamp": "date", "target": "value"}
                    )
                    historical["type"] = "Исторические"
                    
                    forecast_df = item_forecast.reset_index()
                    forecast_df = forecast_df[["timestamp", "0.5"]].rename(
                        columns={"timestamp": "date", "0.5": "value"}
                    )
                    forecast_df["type"] = "Прогноз"
                    
                    # Объединяем в один DataFrame для графика
                    combined = pd.concat([historical, forecast_df], ignore_index=True)
                    graphs_data[item_id] = combined
            
            all_graphs_data[target_column] = graphs_data
        
        prediction_time = time.time() - start_time
        logging.info(f"Предсказание завершено за {prediction_time:.2f} секунд")
        
        # Освобождаем память
        gc.collect()
        
        return {
            'success': True,
            'all_forecasts': all_forecasts,
            'all_graphs_data': all_graphs_data,
            'prediction_time': prediction_time,
            'active_tgt_cols': active_tgt_cols
        }
        
    except Exception as e:
        logging.exception(f"Ошибка при выполнении предсказания: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def run_prediction():
    """Запускает процесс прогнозирования модели"""
    # Проверки входных данных
    if st.session_state.get("predictor") is None:
        st.error("❌ Ошибка: Модель не обучена. Пожалуйста, сначала обучите модель.")
        return
    
    # Получаем параметры прогнозирования
    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col = st.session_state.get("id_col_key")
    
    # Получаем обученный предиктор из сессии
    predictor = st.session_state.get("predictor")
    
    # Отображаем прогресс-бар и сообщение
    with st.spinner("🔄 Выполнение прогноза..."):
        try:
            # Прямой вызов функции прогнозирования
            result = _execute_prediction(
                predictor=predictor,
                dt_col=dt_col,
                tgt_col=tgt_col,
                id_col=id_col if id_col != "<нет>" else None,
            )
            
            if result['success']:
                # Получаем результаты
                all_forecasts = result.get('all_forecasts', {})
                all_graphs_data = result.get('all_graphs_data', {})
                active_tgt_cols = result.get('active_tgt_cols', [])
                
                # Сохраняем результаты в session_state
                for tgt_col in active_tgt_cols:
                    if tgt_col in all_forecasts:
                        forecast_data = all_forecasts[tgt_col]
                        # Сохраняем предсказания
                        st.session_state[f'predictions_{tgt_col}'] = forecast_data['predictions']
                        # Сохраняем флаг дрейфа
                        st.session_state[f'drift_detected_{tgt_col}'] = forecast_data['drift_detected']
                        # Сохраняем информацию о дрейфе
                        st.session_state[f'drift_info_{tgt_col}'] = forecast_data['drift_info']
                        # Сохраняем данные для графиков
                        if tgt_col in all_graphs_data:
                            st.session_state[f'graphs_data_{tgt_col}'] = all_graphs_data[tgt_col]
                
                # Сохраняем список обработанных целевых переменных
                st.session_state['processed_target_cols'] = active_tgt_cols
                
                # Показываем успешное сообщение
                st.success(f"✅ Прогноз успешно выполнен для {len(active_tgt_cols)} переменных!")
                
                # Визуализируем результаты
                st.subheader("📈 Результаты прогноза")
                
                for tgt_col in active_tgt_cols:
                    with st.expander(f"Прогноз для {tgt_col}", expanded=True):
                        # Показываем предупреждение о дрейфе концепции, если он обнаружен
                        if st.session_state.get(f'drift_detected_{tgt_col}', False):
                            st.warning(f"⚠️ Обнаружен дрейф концепции для переменной {tgt_col}!")
                            
                            # Показываем детали дрейфа
                            drift_info = st.session_state.get(f'drift_info_{tgt_col}', {})
                            if drift_info:
                                drift_msg = f"""
                                📊 **Детали дрейфа концепции:**
                                - p-value: {drift_info.get('p_value', 'N/A'):.6f}
                                - Статистика: {drift_info.get('statistic', 'N/A'):.6f}
                                - Порог: {drift_info.get('threshold', 'N/A'):.6f}
                                """
                                st.markdown(drift_msg)
                        
                        # Показываем график для первого ID из данных
                        graphs_data = st.session_state.get(f'graphs_data_{tgt_col}', {})
                        if graphs_data:
                            # Получаем список доступных ID
                            item_ids = list(graphs_data.keys())
                            
                            # Выбор ID для отображения
                            selected_id = st.selectbox(
                                f"Выберите ID для отображения графика ({tgt_col})",
                                options=item_ids,
                                key=f"select_id_{tgt_col}"
                            )
                            
                            # Отображаем график
                            if selected_id in graphs_data:
                                import plotly.express as px
                                combined_data = graphs_data[selected_id]
                                fig = px.line(
                                    combined_data,
                                    x="date",
                                    y="value",
                                    color="type",
                                    title=f"Прогноз для {tgt_col} (ID: {selected_id})",
                                    labels={"value": "Значение", "date": "Дата", "type": "Тип данных"}
                                )
                                # Увеличиваем размер маркеров и толщину линий для лучшей видимости
                                fig.update_traces(mode="lines+markers", marker=dict(size=8), line=dict(width=2))
                                # Увеличиваем высоту графика
                                st.plotly_chart(fig, use_container_width=True, height=600)
                
                # Добавляем кнопку для скачивания результатов
                for tgt_col in active_tgt_cols:
                    predictions = st.session_state.get(f'predictions_{tgt_col}')
                    if predictions is not None:
                        from src.utils.exporter import generate_excel_buffer
                        excel_buffer = generate_excel_buffer(
                            predictions,
                            st.session_state.get('leaderboard'),
                            None,  # static_df_train
                            None   # weighted_ensemble_info
                        )
                        
                        st.download_button(
                            label=f"📥 Скачать результаты для {tgt_col} в Excel",
                            data=excel_buffer.getvalue(),
                            file_name=f"forecast_results_{tgt_col}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"download_{tgt_col}"
                        )
            else:
                # Задача завершилась с ошибкой
                st.error(f"❌ Ошибка при выполнении прогноза: {result.get('error', 'Неизвестная ошибка')}")
        
        except Exception as e:
            st.error(f"❌ Произошла ошибка при выполнении прогноза: {str(e)}")
            logging.exception(f"Ошибка при выполнении прогноза: {e}")
            return



