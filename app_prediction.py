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
from src.utils.exporter import generate_excel_buffer, extract_ensemble_weights
from app_ui import get_base_freq

# Исправляем декоратор с учетом рекомендаций по кешированию Streamlit
@st.cache_data(ttl=3600)  # Кэш действителен 1 час
def get_cached_predictions(_predictions_data):
    """Кэширует только результаты прогнозирования"""
    return _predictions_data

# Фактическая реализация предсказания
def _execute_prediction(
    predictor,
    dt_col,
    tgt_col,
    id_col,
    use_multi_target=False,
    use_holidays=False,
    fill_method="None",
    group_cols_for_fill=None,
    static_feats=None,
    freq=None,
    horizon_val=10,
    generate_report=True,
    detect_drift=True,
    confidence_level=0.95
):
    """
    Выполняет прогнозирование на основе настроек и возвращает результаты.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученная модель предсказания
    dt_col : str
        Имя колонки с датой
    tgt_col : str
        Имя колонки с целевой переменной или список целевых переменных через запятую
    id_col : str
        Имя колонки с идентификатором временного ряда
    use_multi_target : bool, default=False
        Использовать ли несколько целевых переменных
    use_holidays : bool, default=False
        Добавлять ли признак с праздниками
    fill_method : str, default="None"
        Метод заполнения пропусков
    group_cols_for_fill : list, default=None
        Колонки для группировки при заполнении пропусков
    static_feats : list, default=None
        Список колонок для использования как статических признаков
    freq : str, default=None
        Частота данных
    horizon_val : int, default=10
        Горизонт прогнозирования
    generate_report : bool, default=True
        Генерировать ли подробный отчет с метриками моделей
    detect_drift : bool, default=True
        Обнаруживать ли дрейф концепции
    confidence_level : float, default=0.95
        Уровень доверия для обнаружения дрейфа концепции (0.95 = 95%)
        
    Returns:
    --------
    dict
        Словарь с результатами прогнозирования
    """
    try:
        import gc
        from src.models.forecasting import extract_model_metrics
        from time import time
        
        start_time = time()
        
        # Получаем данные из сессии
        df = st.session_state.get("df_data")
        
        if df is None:
            return {
                'success': False,
                'error': "Данные не загружены"
            }
        
        # Если используется несколько целевых переменных, разбиваем строку
        target_columns = tgt_col.split(',') if use_multi_target else [tgt_col]
        
        # Инициализируем словарь для результатов
        result = {
            'success': True,
            'forecasts': {},
            'graphs_data': {},
            'model_metrics': {},
            'parameters': {
                'dt_col': dt_col,
                'id_col': id_col,
                'tgt_col': tgt_col,
                'use_holidays': use_holidays,
                'fill_method': fill_method,
                'prediction_length': horizon_val,
                'freq': freq,
                'confidence_level': confidence_level
            }
        }
        
        # Создаем копию данных для обработки
        df_copy = df.copy()
        
        # Проверяем на наличие необходимых колонок
        required_columns = [dt_col, id_col] + target_columns
        missing_columns = [col for col in required_columns if col not in df_copy.columns]
        
        if missing_columns:
            return {
                'success': False,
                'error': f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}"
            }
        
        # Заполняем пропуски, если указан метод
        if fill_method and fill_method != "None":
            logging.info(f"Заполнение пропусков методом '{fill_method}'")
            
            # Группировка для заполнения пропусков
            if group_cols_for_fill and len(group_cols_for_fill) > 0:
                # Если указаны колонки для группировки, заполняем пропуски в каждой группе
                if fill_method in ["mean", "median"]:
                    # Для mean и median используем transform
                    for target in target_columns:
                        if fill_method == "mean":
                            mean_values = df_copy.groupby(group_cols_for_fill)[target].transform('mean')
                            df_copy[target] = df_copy[target].fillna(mean_values)
                        elif fill_method == "median":
                            median_values = df_copy.groupby(group_cols_for_fill)[target].transform('median')
                            df_copy[target] = df_copy[target].fillna(median_values)
                else:
                    # Для других методов обрабатываем каждую группу по отдельности
                    for target in target_columns:
                        groups = df_copy.groupby(group_cols_for_fill)
                        for _, group in groups:
                            mask = df_copy.loc[group.index, target].isna()
                            
                            if fill_method == "forward":
                                # Заполняем вперед
                                df_copy.loc[group.index, target] = df_copy.loc[group.index, target].fillna(method='ffill')
                            elif fill_method == "backward":
                                # Заполняем назад
                                df_copy.loc[group.index, target] = df_copy.loc[group.index, target].fillna(method='bfill')
                            elif fill_method == "linear":
                                # Линейная интерполяция
                                df_copy.loc[group.index, target] = df_copy.loc[group.index, target].interpolate(method='linear')
            else:
                # Если колонки для группировки не указаны, заполняем пропуски во всем датафрейме
                for target in target_columns:
                    if fill_method == "forward":
                        df_copy[target] = df_copy[target].fillna(method='ffill')
                    elif fill_method == "backward":
                        df_copy[target] = df_copy[target].fillna(method='bfill')
                    elif fill_method == "mean":
                        df_copy[target] = df_copy[target].fillna(df_copy[target].mean())
                    elif fill_method == "median":
                        df_copy[target] = df_copy[target].fillna(df_copy[target].median())
                    elif fill_method == "linear":
                        df_copy[target] = df_copy[target].interpolate(method='linear')
        
        # Преобразуем дату в timestamp, если она не того типа
        if not pd.api.types.is_datetime64_any_dtype(df_copy[dt_col]):
            df_copy[dt_col] = pd.to_datetime(df_copy[dt_col])
        
        # Подготовка исторических данных для обнаружения дрейфа концепции и визуализации
        historical_data = df_copy.copy()
        historical_data.rename(columns={
            id_col: 'item_id',
            dt_col: 'timestamp'
        }, inplace=True)
        
        # Список для хранения данных прогнозов для обнаружения дрейфа
        all_forecasts = {}
        
        # Проходим по каждой целевой переменной
        for target in target_columns:
            try:
                logging.info(f"Выполнение прогноза для целевой переменной: {target}")
                
                # Создаем временной ряд для прогноза
                ts_df = make_timeseries_dataframe(
                    df=df_copy,
                    target_column=target,
                    id_column=id_col,
                    timestamp_column=dt_col,
                    freq=freq
                )
                
                logging.info(f"Создан временной ряд размером {len(ts_df)}")
                
                # Выполняем прогноз
                forecast_start_time = time()
                
                # Получаем прогноз
                forecast = predictor.predict(ts_df, prediction_length=horizon_val)
                
                forecast_time = time() - forecast_start_time
                logging.info(f"Прогноз для {target} выполнен за {forecast_time:.2f}с")
                
                # Формируем словарь с прогнозом
                forecast_info = {
                    'predictions': forecast
                }
                
                # Сохраняем прогноз для обнаружения дрейфа
                forecast_copy = forecast.copy()
                
                # Если это мультииндекс, сбрасываем его для дальнейшей обработки
                if isinstance(forecast_copy.index, pd.MultiIndex):
                    forecast_copy = forecast_copy.reset_index()
                
                # Переименовываем колонки для соответствия стандарту
                if id_col != 'item_id':
                    forecast_copy.rename(columns={id_col: 'item_id'}, inplace=True)
                if dt_col != 'timestamp':
                    forecast_copy.rename(columns={dt_col: 'timestamp'}, inplace=True)
                
                # Сохраняем прогноз для этой целевой переменной
                all_forecasts[target] = forecast_copy
                
                # Получаем метрики модели
                if generate_report:
                    try:
                        logging.info(f"Получение метрик модели для {target}")
                        model_metrics = extract_model_metrics(predictor, test_data=ts_df, predictions=forecast)
                        result['model_metrics'][target] = model_metrics
                    except Exception as metrics_error:
                        logging.warning(f"Ошибка при получении метрик для {target}: {metrics_error}")
                        result['model_metrics'][target] = {
                            'error': str(metrics_error),
                            'model_info': predictor.model_names() if hasattr(predictor, 'model_names') else {}
                        }
                
                # Добавляем результат
                result['forecasts'][target] = forecast_info
                
            except Exception as target_error:
                logging.error(f"Ошибка при прогнозировании {target}: {target_error}")
                import traceback
                traceback.print_exc()
                
                result['forecasts'][target] = {
                    'error': str(target_error)
                }
        
        # Проверка на дрейф концепции
        if detect_drift and all_forecasts:
            try:
                logging.info("Выполняем проверку на дрейф концепции")
                
                # Создаем единый DataFrame для всех прогнозов
                all_forecasts_df = pd.concat(list(all_forecasts.values()), keys=list(all_forecasts.keys()))
                all_forecasts_df = all_forecasts_df.reset_index(level=0).rename(columns={'level_0': 'target_var'})
                
                # Обнаружение дрейфа концепции
                drift_results = detect_concept_drift(
                    historical_data=historical_data,
                    forecasts=all_forecasts_df,
                    target_cols=target_columns,
                    confidence=confidence_level
                )
                
                # Обрабатываем результаты дрейфа для каждой целевой переменной
                for target in target_columns:
                    # Если есть ошибка в прогнозе, пропускаем
                    if 'error' in result['forecasts'][target]:
                        continue
                    
                    # Добавляем информацию о дрейфе в результаты прогноза
                    if drift_results.get('drift_info'):
                        # Выделяем информацию о дрейфе, относящуюся к этой переменной
                        target_drift_info = {}
                        any_drift_for_target = False
                        
                        for item_id, drift_data in drift_results.get('drift_info', {}).items():
                            target_drift_info[item_id] = drift_data
                            if drift_data.get('drift_detected', False):
                                any_drift_for_target = True
                        
                        # Добавляем информацию о дрейфе для этой целевой переменной
                        result['forecasts'][target]['drift_detected'] = any_drift_for_target
                        result['forecasts'][target]['drift_info'] = target_drift_info
                
            except Exception as drift_error:
                logging.error(f"Ошибка при обнаружении дрейфа концепции: {drift_error}")
                import traceback
                traceback.print_exc()
        
        # Подготовка данных для графиков
        try:
            logging.info("Подготовка данных для графиков")
            graphs_data = prepare_graph_data(
                historical_data=historical_data, 
                forecasts=all_forecasts_df if all_forecasts else None, 
                target_cols=target_columns
            )
            
            if graphs_data:
                result['graphs_data'] = graphs_data
        except Exception as graph_error:
            logging.error(f"Ошибка при подготовке данных для графиков: {graph_error}")
            import traceback
            traceback.print_exc()
        
        # Освобождаем память
        del df_copy
        gc.collect()
        
        total_time = time() - start_time
        result['execution_time'] = total_time
        
        logging.info(f"Прогнозирование завершено за {total_time:.2f}с")
        return result
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logging.error(f"Ошибка при выполнении прогнозирования: {e}\n{error_details}")
        
        return {
            'success': False,
            'error': str(e)
        }

def detect_concept_drift(historical_data, forecasts, target_cols=None, confidence=0.95):
    """
    Обнаруживает дрейф концепции между историческими данными и прогнозами.
    
    Parameters:
    -----------
    historical_data : pd.DataFrame
        Исторические данные с колонками (item_id, timestamp, *target_cols)
    forecasts : pd.DataFrame
        Данные прогнозов с аналогичной структурой
    target_cols : list, optional
        Список целевых переменных для проверки
    confidence : float, default=0.95
        Уровень доверия для обнаружения дрейфа
        
    Returns:
    --------
    dict
        Словарь с информацией о дрейфе
    """
    try:
        import pandas as pd
        import numpy as np
        from scipy import stats
        import logging
        
        if target_cols is None:
            # Исключаем служебные колонки
            possible_target_cols = [col for col in historical_data.columns if col not in ['item_id', 'timestamp']]
            if not possible_target_cols:
                return {
                    'drift_detected': False,
                    'error': 'Не найдены целевые переменные в данных',
                    'drift_info': {}
                }
            target_cols = possible_target_cols
        
        # Подготавливаем результирующий словарь
        result = {
            'drift_detected': False,
            'drift_info': {}
        }
        
        # Параметры для определения дрейфа
        threshold_z = stats.norm.ppf(confidence)  # Z-score для выбранного уровня доверия
        threshold_range = 1.5  # Порог для отношения диапазонов
        
        any_drift_detected = False
        
        # Проверяем дрейф для каждого ID и целевой переменной
        for target_col in target_cols:
            # Получаем уникальные ID из обоих наборов данных
            historical_ids = historical_data['item_id'].unique()
            forecast_ids = forecasts['item_id'].unique()
            
            # Обрабатываем только ID, присутствующие в обоих наборах
            common_ids = list(set(historical_ids) & set(forecast_ids))
            
            for item_id in common_ids:
                # Получаем данные для текущего ID
                hist_values = historical_data[historical_data['item_id'] == item_id][target_col].values
                forecast_values = forecasts[forecasts['item_id'] == item_id][target_col].values
                
                # Пропускаем, если недостаточно данных
                if len(hist_values) < 2 or len(forecast_values) < 2:
                    continue
                
                # Рассчитываем базовые статистики
                historical_mean = np.mean(hist_values)
                forecast_mean = np.mean(forecast_values)
                
                historical_std = np.std(hist_values, ddof=1)
                forecast_std = np.std(forecast_values, ddof=1)
                
                historical_min = np.min(hist_values)
                forecast_min = np.min(forecast_values)
                
                historical_max = np.max(hist_values)
                forecast_max = np.max(forecast_values)
                
                historical_range = historical_max - historical_min
                forecast_range = forecast_max - forecast_min
                
                # Список для сохранения причин дрейфа
                drift_reasons = []
                
                # Проверяем среднее значение
                if historical_std > 0:
                    z_score = abs(forecast_mean - historical_mean) / historical_std
                    
                    # Проверяем Z-score
                    if z_score > threshold_z:
                        direction = "выше" if forecast_mean > historical_mean else "ниже"
                        drift_reasons.append({
                            "reason": f"Значительное изменение среднего значения ({direction})",
                            "details": f"Z-score: {z_score:.2f} > {threshold_z:.2f}, историческое среднее: {historical_mean:.2f}, прогнозное среднее: {forecast_mean:.2f}"
                        })
                else:
                    z_score = None
                
                # Проверяем отношение диапазонов
                if historical_range > 0:
                    range_stretch = forecast_range / historical_range
                    
                    # Проверяем отношение диапазонов
                    if range_stretch > threshold_range:
                        drift_reasons.append({
                            "reason": "Расширение диапазона значений",
                            "details": f"Отношение: {range_stretch:.2f} > {threshold_range}, исторический диапазон: [{historical_min:.2f}, {historical_max:.2f}], прогнозный диапазон: [{forecast_min:.2f}, {forecast_max:.2f}]"
                        })
                else:
                    range_stretch = None
                
                # Проверяем изменения в дисперсии
                if historical_std > 0 and forecast_std > 0:
                    var_ratio = (forecast_std / historical_std) ** 2
                    
                    if var_ratio > 2.0:
                        drift_reasons.append({
                            "reason": "Увеличение волатильности",
                            "details": f"Отношение дисперсий: {var_ratio:.2f} > 2.0, историческое стд. отклонение: {historical_std:.2f}, прогнозное стд. отклонение: {forecast_std:.2f}"
                        })
                    elif var_ratio < 0.5:
                        drift_reasons.append({
                            "reason": "Уменьшение волатильности",
                            "details": f"Отношение дисперсий: {var_ratio:.2f} < 0.5, историческое стд. отклонение: {historical_std:.2f}, прогнозное стд. отклонение: {forecast_std:.2f}"
                        })
                
                # Определяем, обнаружен ли дрейф
                is_drift_detected = len(drift_reasons) > 0
                
                # Если обнаружен хотя бы один дрейф
                if is_drift_detected:
                    any_drift_detected = True
                
                # Сохраняем информацию о дрейфе для данного ID
                result['drift_info'][item_id] = {
                    'drift_detected': is_drift_detected,
                    'drift_reasons': drift_reasons,
                    'historical_stats': {
                        'mean': historical_mean,
                        'std': historical_std,
                        'min': historical_min,
                        'max': historical_max,
                        'range': historical_range
                    },
                    'forecast_stats': {
                        'mean': forecast_mean,
                        'std': forecast_std,
                        'min': forecast_min,
                        'max': forecast_max,
                        'range': forecast_range
                    },
                    'metrics': {
                        'z_score': z_score,
                        'range_stretch': range_stretch
                    }
                }
        
        # Обновляем общий результат
        result['drift_detected'] = any_drift_detected
        
        return result
    
    except Exception as e:
        logging.exception(f"Ошибка при определении дрейфа концепции: {e}")
        return {
            'drift_detected': False,
            'error': str(e),
            'drift_info': {}
        }

def prepare_graph_data(historical_data, forecasts, target_cols=None):
    """
    Подготавливает данные для визуализации прогнозов

    Parameters:
    -----------
    historical_data : pd.DataFrame
        Исторические данные для визуализации
    forecasts : pd.DataFrame
        Данные прогнозов с аналогичной структурой
    target_cols : list, optional
        Список целевых переменных для визуализации. 
        Если None, будут использованы все целевые переменные из прогнозов.
    
    Returns:
    --------
    dict
        Словарь с данными для визуализации для каждой целевой переменной и ID
    """
    import pandas as pd
    import numpy as np
    import logging
    
    try:
        # Инициализируем результат
        result = {}
        
        if forecasts is None or historical_data is None:
            logging.warning("Невозможно подготовить данные для графиков: отсутствуют необходимые данные")
            return result
        
        # Если target_cols не передан, используем все доступные целевые переменные из данных
        if target_cols is None and 'target_var' in forecasts.columns:
            target_cols = forecasts['target_var'].unique().tolist()
        
        if not target_cols:
            logging.warning("Не удалось определить целевые переменные для визуализации")
            return result
        
        # Обрабатываем каждую целевую переменную
        for target_col in target_cols:
            # Создаем словарь для данной целевой переменной
            result[target_col] = {}
            
            # Фильтруем прогнозы для текущей целевой переменной
            if 'target_var' in forecasts.columns:
                target_forecasts = forecasts[forecasts['target_var'] == target_col]
            else:
                # Предполагаем, что все прогнозы относятся к одной переменной
                target_forecasts = forecasts
            
            if target_forecasts.empty:
                logging.warning(f"Нет прогнозов для целевой переменной {target_col}")
                continue
            
            # Получаем список уникальных ID из прогноза
            if 'item_id' in target_forecasts.columns:
                item_ids = target_forecasts['item_id'].unique()
            else:
                logging.warning(f"Невозможно найти идентификаторы рядов в прогнозах для {target_col}")
                continue
            
            # Обрабатываем каждый ID
            for item_id in item_ids:
                # Фильтруем исторические данные для текущего ID
                if 'item_id' in historical_data.columns:
                    history = historical_data[historical_data['item_id'] == item_id].copy()
                else:
                    logging.warning(f"Не удалось найти item_id в исторических данных для ID {item_id}")
                    continue
                
                # Фильтруем прогнозы для текущего ID
                forecast = target_forecasts[target_forecasts['item_id'] == item_id].copy()
                
                if history.empty or forecast.empty:
                    logging.warning(f"Нет данных для визуализации для ID {item_id} и переменной {target_col}")
                    continue
                
                # Убеждаемся, что timestamp имеет правильный тип
                for df in [history, forecast]:
                    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                        try:
                            df['timestamp'] = pd.to_datetime(df['timestamp'])
                        except Exception as e:
                            logging.warning(f"Не удалось преобразовать timestamp к типу datetime для ID {item_id}: {e}")
                            continue
                
                # Определяем колонки с данными
                target_col_in_history = target_col
                if target_col not in history.columns:
                    # Ищем колонку target в истории
                    if 'target' in history.columns:
                        target_col_in_history = 'target'
                    else:
                        logging.warning(f"Не удалось найти колонку с целевой переменной {target_col} в исторических данных")
                        continue
                
                # Определяем колонку с данными в прогнозе
                forecast_value_col = None
                for col in forecast.columns:
                    if any(keyword in str(col).lower() for keyword in ['mean', 'prediction', 'forecast', 'value', 'target']):
                        forecast_value_col = col
                        break
                
                if forecast_value_col is None and len(forecast.columns) > 2:  # предполагаем, что первые 2 колонки - item_id и timestamp
                    # Просто берем третью колонку, предполагая, что это значение прогноза
                    forecast_value_col = forecast.columns[2]
                
                if forecast_value_col is None:
                    logging.warning(f"Не удалось определить колонку с прогнозом для ID {item_id}")
                    continue
                
                # Определяем колонки с доверительными интервалами
                lower_col = None
                upper_col = None
                
                for col in forecast.columns:
                    col_str = str(col).lower()
                    if any(keyword in col_str for keyword in ['lower', 'lo', 'min', '0.1']):
                        lower_col = col
                    elif any(keyword in col_str for keyword in ['upper', 'hi', 'max', '0.9']):
                        upper_col = col
                
                # Создаем DataFrame для визуализации исторических данных
                historical_plot_data = pd.DataFrame({
                    'date': history['timestamp'],
                    'value': history[target_col_in_history],
                    'type': 'История',
                    'lower': None,
                    'upper': None
                })
                
                # Создаем DataFrame для визуализации прогноза
                forecast_plot_data = pd.DataFrame({
                    'date': forecast['timestamp'],
                    'value': forecast[forecast_value_col],
                    'type': 'Прогноз',
                    'lower': forecast[lower_col] if lower_col is not None else None,
                    'upper': forecast[upper_col] if upper_col is not None else None
                })
                
                # Объединяем исторические данные и прогноз
                plot_data = pd.concat([historical_plot_data, forecast_plot_data], ignore_index=True)
                
                # Сохраняем данные для визуализации
                result[target_col][item_id] = plot_data
        
        return result
    except Exception as e:
        logging.error(f"Ошибка при подготовке данных для графиков: {e}")
        import traceback
        traceback.print_exc()
        return {}

def display_prediction_results(result):
    """
    Отображает результаты прогнозирования в интерфейсе.
    
    Parameters:
    -----------
    result : dict
        Словарь с результатами прогнозирования
    """
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        import pandas as pd
        from datetime import datetime
        
        if not result.get('success', False):
            st.error(f"Ошибка при выполнении прогнозирования: {result.get('error', 'Неизвестная ошибка')}")
            return
        
        # Получаем данные прогнозов для каждой целевой переменной
        forecasts = result.get('forecasts', {})
        
        if not forecasts:
            st.warning("Результаты прогнозирования не содержат прогнозов для целевых переменных.")
            return
        
        # Проверяем наличие метрик модели
        model_metrics = result.get('model_metrics', {})
        
        # Отображаем дашборд для каждой целевой переменной
        for target_col, forecast_data in forecasts.items():
            st.subheader(f"Результаты прогнозирования: {target_col}")
            
            # Проверяем на наличие ошибки в прогнозе
            if 'error' in forecast_data:
                st.error(f"Ошибка при прогнозировании для {target_col}: {forecast_data['error']}")
                continue
            
            # Получаем прогноз
            predictions = forecast_data.get('predictions', None)
            
            if predictions is None:
                st.warning(f"Прогноз для {target_col} не содержит предсказаний.")
                continue
            
            # Проверяем на наличие информации о дрейфе концепции
            drift_detected = forecast_data.get('drift_detected', False)
            drift_info = forecast_data.get('drift_info', {})
            
            # Отображаем предупреждение о дрейфе концепции, если он обнаружен
            if drift_detected:
                st.warning(
                    "⚠️ **Обнаружен дрейф концепции!** Распределение прогнозируемых значений существенно " +
                    "отличается от обучающей выборки. Рекомендуется проверить данные и, возможно, переобучить модель."
                )
                
                # Отображаем детали дрейфа концепции
                with st.expander("Подробности о дрейфе концепции", expanded=True):
                    # Создаем таблицу с информацией о дрейфе для разных ID
                    drift_rows = []
                    
                    for item_id, drift_data in drift_info.items():
                        if drift_data.get('drift_detected', False):
                            # Извлекаем причины дрейфа
                            reasons = []
                            for reason_data in drift_data.get('drift_reasons', []):
                                if isinstance(reason_data, dict):
                                    reasons.append(reason_data.get('reason', ''))
                                else:
                                    reasons.append(str(reason_data))
                            
                            # Формируем строку таблицы для каждого ID с дрейфом
                            hist_stats = drift_data.get('historical_stats', {})
                            forecast_stats = drift_data.get('forecast_stats', {})
                            
                            row = {
                                'ID': item_id,
                                'Причины': ", ".join(reasons),
                                'Среднее (обучение)': f"{hist_stats.get('mean', 0):.2f}",
                                'Среднее (прогноз)': f"{forecast_stats.get('mean', 0):.2f}",
                                'Мин-Макс (обучение)': f"{hist_stats.get('min', 0):.2f} - {hist_stats.get('max', 0):.2f}",
                                'Мин-Макс (прогноз)': f"{forecast_stats.get('min', 0):.2f} - {forecast_stats.get('max', 0):.2f}"
                            }
                            drift_rows.append(row)
                    
                    if drift_rows:
                        # Создаем DataFrame с информацией о дрейфе и отображаем его
                        drift_df = pd.DataFrame(drift_rows)
                        st.dataframe(drift_df)
                    else:
                        st.write("Нет информации о дрейфе концепции.")
            
            # Отображаем метрики модели для данной целевой переменной, если они есть
            if target_col in model_metrics:
                with st.expander("Метрики модели", expanded=True):
                    metrics = model_metrics[target_col]
                    
                    if 'error' in metrics:
                        st.warning(f"Не удалось получить полные метрики: {metrics['error']}")
                    
                    # Отображаем информацию о модели
                    if 'model_info' in metrics:
                        model_info = metrics['model_info']
                        
                        st.write("**Информация о модели:**")
                        
                        # Создаем таблицу с информацией о модели
                        info_data = []
                        
                        for key, value in model_info.items():
                            # Пропускаем слишком большие или сложные значения
                            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                                continue
                                
                            info_data.append({
                                'Параметр': key,
                                'Значение': str(value)
                            })
                        
                        if info_data:
                            # Создаем DataFrame и отображаем его
                            info_df = pd.DataFrame(info_data)
                            st.dataframe(info_df)
                    
                    # Отображаем таблицу лидеров, если она есть
                    if 'leaderboard' in metrics and isinstance(metrics['leaderboard'], pd.DataFrame):
                        st.write("**Таблица лидеров:**")
                        st.dataframe(metrics['leaderboard'])
                    
                    # Отображаем другие метрики
                    if 'evaluation_metrics' in metrics:
                        st.write("**Метрики оценки:**")
                        st.json(metrics['evaluation_metrics'])
            
            # Отображаем графики прогнозов
            graphs_data = result.get('graphs_data', {}).get(target_col, {})
            
            if graphs_data:
                st.write("**Графики прогнозов:**")
                
                # Список ID для отображения
                item_ids = list(graphs_data.keys())
                
                # Создаем многостраничное отображение для графиков
                tabs = st.tabs([f"ID: {item_id}" for item_id in item_ids])
                
                # Для каждого ID создаем вкладку с графиком
                for i, item_id in enumerate(item_ids):
                    with tabs[i]:
                        plot_data = graphs_data[item_id]
                        
                        # Проверяем, есть ли данные для графика
                        if plot_data.empty:
                            st.warning(f"Нет данных для отображения графика для ID {item_id}")
                            continue
                        
                        # Форматируем даты в строки для отображения
                        plot_data['date_str'] = plot_data['date'].dt.strftime('%Y-%m-%d')
                        
                        # Проверяем наличие дрейфа для этого ID
                        item_drift_detected = False
                        if drift_info and item_id in drift_info:
                            item_drift_detected = drift_info[item_id].get('drift_detected', False)
                        
                        # Создаем интерактивный график с помощью plotly
                        fig = go.Figure()
                        
                        # Добавляем исторические данные
                        historical = plot_data[plot_data['type'] == 'История']
                        if not historical.empty:
                            fig.add_trace(go.Scatter(
                                x=historical['date'],
                                y=historical['value'],
                                mode='lines+markers',
                                name='Исторические данные',
                                line=dict(color='blue')
                            ))
                        
                        # Добавляем прогноз
                        forecast = plot_data[plot_data['type'] == 'Прогноз']
                        if not forecast.empty:
                            fig.add_trace(go.Scatter(
                                x=forecast['date'],
                                y=forecast['value'],
                                mode='lines+markers',
                                name='Прогноз',
                                line=dict(color='red', dash='dot')
                            ))
                            
                            # Добавляем доверительный интервал, если он есть
                            if 'lower' in forecast.columns and 'upper' in forecast.columns:
                                # Удаляем строки, где lower или upper равны None
                                forecast_interval = forecast.dropna(subset=['lower', 'upper'])
                                
                                if not forecast_interval.empty:
                                    fig.add_trace(go.Scatter(
                                        x=forecast_interval['date'],
                                        y=forecast_interval['upper'],
                                        mode='lines',
                                        line=dict(width=0),
                                        showlegend=False
                                    ))
                                    
                                    fig.add_trace(go.Scatter(
                                        x=forecast_interval['date'],
                                        y=forecast_interval['lower'],
                                        mode='lines',
                                        line=dict(width=0),
                                        fillcolor='rgba(255, 0, 0, 0.2)',
                                        fill='tonexty',
                                        name='90% интервал'
                                    ))
                        
                        # Настраиваем внешний вид графика
                        title = f'Прогноз для ID {item_id}'
                        if item_drift_detected:
                            title += ' ⚠️ (Обнаружен дрейф концепции)'
                        
                        fig.update_layout(
                            title=title,
                            xaxis_title='Дата',
                            yaxis_title='Значение',
                            hovermode='x unified',
                            template='plotly_white'
                        )
                        
                        # Отображаем график
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Если обнаружен дрейф для этого ID, отображаем детали
                        if item_drift_detected and item_id in drift_info:
                            drift_details = drift_info[item_id]
                            hist_stats = drift_details.get('historical_stats', {})
                            forecast_stats = drift_details.get('forecast_stats', {})
                            
                            st.warning("⚠️ **Для этого временного ряда обнаружен дрейф концепции!**")
                            
                            # Выводим детали причин дрейфа
                            st.write("**Причины дрейфа:**")
                            for reason_data in drift_details.get('drift_reasons', []):
                                if isinstance(reason_data, dict):
                                    st.markdown(f"- **{reason_data.get('reason', '')}**")
                                    if 'details' in reason_data:
                                        st.markdown(f"  {reason_data.get('details', '')}")
                                else:
                                    st.markdown(f"- {str(reason_data)}")
                            
                            # Выводим таблицу сравнения статистик
                            stats_data = [
                                {"Статистика": "Среднее", "Исторические данные": f"{hist_stats.get('mean', 0):.2f}", "Прогноз": f"{forecast_stats.get('mean', 0):.2f}"},
                                {"Статистика": "Минимум", "Исторические данные": f"{hist_stats.get('min', 0):.2f}", "Прогноз": f"{forecast_stats.get('min', 0):.2f}"},
                                {"Статистика": "Максимум", "Исторические данные": f"{hist_stats.get('max', 0):.2f}", "Прогноз": f"{forecast_stats.get('max', 0):.2f}"},
                                {"Статистика": "Диапазон", "Исторические данные": f"{hist_stats.get('range', 0):.2f}", "Прогноз": f"{forecast_stats.get('range', 0):.2f}"}
                            ]
                            stats_df = pd.DataFrame(stats_data)
                            st.write("**Сравнение статистик:**")
                            st.dataframe(stats_df)
                            
                            
            else:
                st.warning(f"Нет данных для визуализации прогноза для {target_col}")
    
    except Exception as e:
        import traceback
        st.error(f"Ошибка при отображении результатов: {e}")
        st.exception(e)

def run_prediction():
    """
    Запускает процесс прогнозирования на основе настроек пользователя и отображает результаты.
    """
    try:
        import os
        import time
        import pandas as pd
        import logging
        from autogluon.timeseries import TimeSeriesPredictor
        from datetime import datetime
        from src.data_processing.timeseries_utils import make_timeseries_dataframe
        from src.utils.export import generate_excel_report
        
        # Настраиваем страницу Streamlit
        st.title("Прогнозирование временных рядов")
        
        # Проверяем, загружены ли данные
        if "df_data" not in st.session_state or st.session_state.get("df_data") is None:
            st.error("Данные не загружены. Пожалуйста, загрузите данные во вкладке 'Данные'.")
            st.stop()
        
        # Проверяем, есть ли модели
        models_dir = "models"
        if not os.path.exists(models_dir) or len([f for f in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, f))]) == 0:
            st.error("Нет доступных моделей. Пожалуйста, обучите модель во вкладке 'Обучение'.")
            st.stop()
        
        # Получаем список моделей
        models = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
        
        # Контейнер для настроек
        with st.expander("Настройки прогнозирования", expanded=True):
            # Выбор модели
            model_name = st.selectbox(
                "Выберите модель",
                options=models,
                format_func=lambda x: x.replace("_", " ").title(),
                help="Выберите обученную модель для прогнозирования"
            )
            
            # Определяем путь к выбранной модели
            model_path = os.path.join(models_dir, model_name)
            
            # Мета-информация о модели
            if os.path.exists(os.path.join(model_path, "metadata.json")):
                import json
                with open(os.path.join(model_path, "metadata.json"), "r") as f:
                    metadata = json.load(f)
                    
                # Отображаем основную информацию о модели
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"📅 Дата создания: {metadata.get('created_at', 'Н/Д')}")
                with col2:
                    st.info(f"🎯 Целевая переменная: {metadata.get('target_column', 'Н/Д')}")
                with col3:
                    freq = metadata.get('frequency', 'Н/Д')
                    st.info(f"⏱️ Частота: {freq}")
                
                # Дополнительная информация
                with st.expander("Дополнительная информация о модели", expanded=False):
                    # Создаем DataFrame с метаданными
                    meta_items = []
                    for key, value in metadata.items():
                        if key not in ["created_at", "target_column", "frequency"]:
                            # Пропускаем слишком большие или сложные значения
                            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                                value = str(value)[:100] + "..."
                                
                            meta_items.append({
                                "Параметр": key,
                                "Значение": value
                            })
                    
                    if meta_items:
                        meta_df = pd.DataFrame(meta_items)
                        st.dataframe(meta_df)
                    else:
                        st.write("Нет дополнительных метаданных")
            
            # Горизонт прогнозирования
            horizon = st.number_input(
                "Горизонт прогнозирования",
                min_value=1,
                max_value=365,
                value=metadata.get("prediction_length", 10) if "metadata" in locals() else 10,
                help="Количество временных шагов для прогнозирования"
            )
            
            # Если есть метаданные, используем их для определения колонок
            if "metadata" in locals():
                id_col_default = metadata.get("id_column", "")
                dt_col_default = metadata.get("timestamp_column", "")
                target_col_default = metadata.get("target_column", "")
                use_multi_target_default = metadata.get("use_multi_target", False)
            else:
                id_col_default = ""
                dt_col_default = ""
                target_col_default = ""
                use_multi_target_default = False
            
            # Выбор колонок
            col1, col2 = st.columns(2)
            with col1:
                id_col = st.text_input("Колонка с ID", value=id_col_default, help="Имя колонки с идентификаторами временных рядов")
                target_col = st.text_input("Целевая колонка", value=target_col_default, help="Имя колонки с целевой переменной")
            with col2:
                dt_col = st.text_input("Колонка с датой", value=dt_col_default, help="Имя колонки с временными метками")
                use_multi_target = st.checkbox("Использовать несколько целевых колонок", value=use_multi_target_default, help="Если включено, целевую колонку можно указать как список через запятую")
            
            # Тип заполнения пропусков
            fill_method = st.selectbox(
                "Метод заполнения пропусков",
                options=["None", "forward", "backward", "mean", "median", "linear"],
                format_func=lambda x: {
                    "None": "Не заполнять",
                    "forward": "Предыдущим значением",
                    "backward": "Следующим значением",
                    "mean": "Средним",
                    "median": "Медианой",
                    "linear": "Линейной интерполяцией"
                }.get(x, x),
                help="Метод заполнения пропущенных значений в данных"
            )
            
            # Если выбран метод заполнения, показываем опцию группировки
            if fill_method != "None":
                # Получаем список колонок из данных
                df_columns = st.session_state.get("df_data").columns.tolist()
                
                group_cols_for_fill = st.multiselect(
                    "Группировать при заполнении по",
                    options=df_columns,
                    default=[id_col] if id_col in df_columns else [],
                    help="Выберите колонки для группировки при заполнении пропусков. Если не выбрано, заполнение будет выполняться по всему датасету."
                )
            else:
                group_cols_for_fill = None
            
            # Добавление праздников
            use_holidays = st.checkbox(
                "Добавить праздники",
                value=False,
                help="Добавить признаки праздников для повышения точности прогноза"
            )
            
            # Выбор статичных признаков
            if "metadata" in locals() and "features" in metadata:
                features = metadata.get("features", [])
                
                if features:
                    static_feats = st.multiselect(
                        "Статические признаки",
                        options=features,
                        default=[],
                        help="Выберите статические признаки для включения в модель"
                    )
                else:
                    static_feats = None
            else:
                static_feats = None
            
            # Настройки генерации отчета
            with st.expander("Настройки отчета", expanded=False):
                generate_report = st.checkbox(
                    "Генерировать подробный отчет с метриками",
                    value=True,
                    help="Если включено, будет сгенерирован подробный отчет с метриками моделей"
                )
                
                # Опции для генерации Excel-отчета
                generate_excel = st.checkbox(
                    "Сохранить результаты в Excel",
                    value=False,
                    help="Если включено, результаты прогнозирования будут сохранены в Excel-файл"
                )
                
                if generate_excel:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        include_leaderboard = st.checkbox(
                            "Включить таблицу лидеров",
                            value=True,
                            help="Добавить в отчет таблицу лидеров с метриками всех моделей"
                        )
                        
                        include_model_info = st.checkbox(
                            "Включить информацию о модели",
                            value=True,
                            help="Добавить в отчет информацию о модели и её параметрах"
                        )
                    
                    with col2:
                        include_graphs = st.checkbox(
                            "Включить графики",
                            value=True,
                            help="Добавить в отчет графики прогнозов"
                        )
                        
                        include_individual_models = st.checkbox(
                            "Включить индивидуальные модели",
                            value=False,
                            help="Добавить в отчет информацию об индивидуальных моделях и их гиперпараметрах"
                        )
            
            # Настройки обнаружения дрейфа концепции
            with st.expander("Настройки обнаружения дрейфа концепции", expanded=False):
                detect_drift = st.checkbox(
                    "Выполнять проверку на дрейф концепции",
                    value=True,
                    help="Если включено, будет выполнена проверка на дрейф концепции в прогнозах"
                )
                
                if detect_drift:
                    confidence_level = st.slider(
                        "Уровень доверия (%)",
                        min_value=80,
                        max_value=99,
                        value=95,
                        step=1,
                        help="Уровень доверия для обнаружения дрейфа концепции (чем выше, тем строже критерий)"
                    )
        
        # Кнопка для запуска прогнозирования
        col_button, col_info = st.columns([1, 4])
        
        with col_button:
            run_button = st.button("Запустить прогнозирование", type="primary", use_container_width=True)
            
        # Если кнопка нажата, выполняем прогноз
        if run_button:
            with st.spinner("Выполняется прогнозирование..."):
                try:
                    # Путь к предиктору
                    predictor_path = model_path
                    
                    # Проверяем, существует ли файл предиктора
                    if not os.path.exists(os.path.join(predictor_path, "predictor.ag")):
                        st.error(f"Файл предиктора не найден: {os.path.join(predictor_path, 'predictor.ag')}")
                        st.stop()
                    
                    # Получаем частоту из метаданных
                    freq = metadata.get("frequency", None) if "metadata" in locals() else None
                    
                    # Загружаем предиктор
                    logging.info(f"Загрузка предиктора из {predictor_path}")
                    predictor = TimeSeriesPredictor.load(predictor_path)
                    
                    # Выполняем прогноз с указанными параметрами
                    prediction_result = _execute_prediction(
                        predictor=predictor,
                        dt_col=dt_col,
                        tgt_col=target_col,
                        id_col=id_col,
                        use_multi_target=use_multi_target,
                        use_holidays=use_holidays,
                        fill_method=fill_method,
                        group_cols_for_fill=group_cols_for_fill,
                        static_feats=static_feats,
                        freq=freq,
                        horizon_val=horizon,
                        generate_report=generate_report,
                        detect_drift=detect_drift,
                        confidence_level=confidence_level / 100 if detect_drift else 0.95
                    )
                    
                    # Если прогноз успешен, отображаем результаты
                    if prediction_result.get('success', False):
                        # Отображаем результаты прогнозирования
                        display_prediction_results(prediction_result)
                        
                        # Если нужно сохранить результаты в Excel, делаем это
                        if generate_excel:
                            try:
                                # Генерируем имя файла с текущей датой и временем
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                excel_file = f"reports/forecast_{model_name}_{timestamp}.xlsx"
                                
                                # Создаем директорию, если она не существует
                                os.makedirs(os.path.dirname(excel_file), exist_ok=True)
                                
                                # Генерируем отчет в Excel
                                with st.spinner("Генерация Excel-отчета..."):
                                    generate_excel_report(
                                        excel_file=excel_file,
                                        result=prediction_result,
                                        model_name=model_name,
                                        include_leaderboard=include_leaderboard,
                                        include_model_info=include_model_info,
                                        include_individual_models=include_individual_models,
                                        include_graphs=include_graphs
                                    )
                                
                                # Отображаем ссылку для скачивания
                                with open(excel_file, "rb") as f:
                                    st.download_button(
                                        label=f"📊 Скачать отчет Excel",
                                        data=f,
                                        file_name=os.path.basename(excel_file),
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            except Exception as excel_error:
                                st.error(f"Ошибка при создании Excel-отчета: {excel_error}")
                                logging.exception(f"Ошибка при создании Excel-отчета: {excel_error}")
                        
                        # Сохраняем результаты в кэше для возможности повторного использования
                        st.session_state["prediction_results"] = prediction_result
                    
                    else:
                        st.error(f"Ошибка при выполнении прогнозирования: {prediction_result.get('error', 'Неизвестная ошибка')}")
                        
                        # Если есть рекомендации, отображаем их
                        if 'recommendations' in prediction_result:
                            st.info("📝 Рекомендации:")
                            for rec in prediction_result['recommendations']:
                                st.markdown(f"- {rec}")
                
                except Exception as e:
                    import traceback
                    st.error(f"Ошибка при прогнозировании: {e}")
                    st.exception(e)
                
        else:
            # Если прогноз уже выполнен ранее и результаты есть в кэше, отображаем их
            if "prediction_results" in st.session_state:
                st.info("Отображаются результаты предыдущего прогноза. Нажмите 'Запустить прогнозирование' для обновления.")
                display_prediction_results(st.session_state["prediction_results"])
    
    except Exception as e:
        import traceback
        st.error(f"Ошибка при прогнозировании: {e}")
        st.exception(e)