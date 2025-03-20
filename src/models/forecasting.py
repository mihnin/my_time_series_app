import os
from typing import Dict, Any, List, Optional, Tuple, Union
import logging
from pathlib import Path

from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
import pandas as pd
import numpy as np
import tempfile
import time

def make_timeseries_dataframe(df, static_features=None, freq='D', id_column=None, timestamp_column=None, target_column=None):
    """
    Создаёт TimeSeriesDataFrame с улучшенной обработкой ошибок
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм с данными временного ряда.
    static_features : pandas.DataFrame, опционально
        Датафрейм со статическими признаками (постоянными для каждого item_id).
    freq : str, опционально
        Частота временного ряда ('D' по умолчанию для daily)
    id_column : str, опционально
        Имя колонки с идентификаторами временных рядов (по умолчанию 'item_id')
    timestamp_column : str, опционально
        Имя колонки с временными метками (по умолчанию 'timestamp')
    target_column : str, опционально
        Имя колонки с целевой переменной (по умолчанию 'target')
    
    Returns:
    --------
    TimeSeriesDataFrame
        TimeSeriesDataFrame для использования в AutoGluon.
    """
    try:
        # Создаем рабочую копию датафрейма
        df_copy = df.copy()
        
        # Переименовываем колонки, если заданы пользовательские имена
        if id_column and id_column != "item_id":
            if id_column not in df_copy.columns:
                raise ValueError(f"Колонка ID {id_column} не найдена в данных")
            logging.info(f"Переименовываем колонку ID из {id_column} в 'item_id'")
            df_copy.rename(columns={id_column: 'item_id'}, inplace=True)
            
        if timestamp_column and timestamp_column != "timestamp":
            if timestamp_column not in df_copy.columns:
                raise ValueError(f"Колонка временных меток {timestamp_column} не найдена в данных")
            logging.info(f"Переименовываем колонку временных меток из {timestamp_column} в 'timestamp'")
            df_copy.rename(columns={timestamp_column: 'timestamp'}, inplace=True)
            
        if target_column and target_column != "target":
            if target_column not in df_copy.columns:
                raise ValueError(f"Колонка целевой переменной {target_column} не найдена в данных")
            logging.info(f"Переименовываем колонку целевой переменной из {target_column} в 'target'")
            df_copy.rename(columns={target_column: 'target'}, inplace=True)
        
        # Проверка необходимых колонок
        required_cols = ["item_id", "timestamp", "target"]
        for col in required_cols:
            if col not in df_copy.columns:
                raise ValueError(f"Отсутствует обязательная колонка: {col}")
        
        # Проверка типа данных для timestamp
        if not pd.api.types.is_datetime64_any_dtype(df_copy["timestamp"]):
            logging.warning("Колонка timestamp не имеет тип datetime64. Преобразуем...")
            df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"], errors="coerce")
            
            # Проверяем успешность преобразования
            if df_copy["timestamp"].isna().any():
                failed_values = df_copy.loc[df_copy["timestamp"].isna(), "timestamp"].head(5).tolist()
                logging.error(f"Не удалось преобразовать некоторые значения даты: {failed_values}")
                raise ValueError("Ошибка преобразования timestamp в datetime")
        
        # Проверка на дубликаты
        duplicate_pairs = df_copy.duplicated(subset=["item_id", "timestamp"]).sum()
        if duplicate_pairs > 0:
            logging.warning(f"Найдены дубликаты в парах item_id-timestamp: {duplicate_pairs}. Удаляем...")
            df_copy = df_copy.drop_duplicates(subset=["item_id", "timestamp"])
        
        # Проверка на пропуски в целевой переменной
        num_missing = df_copy["target"].isna().sum()
        if num_missing > 0:
            missing_percent = 100 * num_missing / len(df_copy)
            logging.warning(f"В колонке target есть пропуски: {num_missing} ({missing_percent:.2f}%)")
            # Здесь можно добавить автоматическое заполнение пропусков, если нужно
        
        # Создаем TimeSeriesDataFrame
        ts_df = TimeSeriesDataFrame(df_copy, static_features=static_features)
        
        # Устанавливаем частоту, если указана и не auto
        if freq and freq.lower() != 'auto':
            # Очистка частоты от русского описания
            if " " in freq:
                freq = freq.split(" ")[0]
            if "(" in freq:
                freq = freq.split("(")[0].strip()
            
            try:
                logging.info(f"Устанавливаем частоту {freq} для TimeSeriesDataFrame")
                ts_df = ts_df.convert_frequency(freq=freq)
            except Exception as freq_err:
                logging.warning(f"Не удалось установить частоту {freq}: {freq_err}")
                # Пытаемся определить частоту автоматически
                try:
                    inferred_freq = pd.infer_freq(
                        df_copy.loc[df_copy["item_id"] == df_copy["item_id"].iloc[0]]["timestamp"]
                    )
                    if inferred_freq:
                        logging.info(f"Автоматически определена частота: {inferred_freq}")
                        ts_df = ts_df.convert_frequency(freq=inferred_freq)
                    else:
                        logging.warning("Не удалось автоматически определить частоту, используем по умолчанию")
                except Exception as auto_freq_err:
                    logging.warning(f"Ошибка при автоопределении частоты: {auto_freq_err}")
        
        logging.info(f"TimeSeriesDataFrame успешно создан: {len(ts_df)} рядов, частота: {ts_df.freq}")
        return ts_df
        
    except Exception as e:
        logging.error(f"Ошибка при создании TimeSeriesDataFrame: {e}")
        
        # Детальное логирование для отладки
        try:
            logging.debug(f"Форма DataFrame: {df.shape}")
            logging.debug(f"Колонки DataFrame: {df.columns.tolist()}")
            if df.index.name:
                logging.debug(f"Имя индекса: {df.index.name}")
            
            # Проверка типов данных
            for col in df.columns:
                logging.debug(f"Колонка {col}: тип {df[col].dtype}")
                
            # Примеры данных
            logging.debug(f"Примеры данных:\n{df.head(3)}")
                
        except Exception as debug_err:
            logging.error(f"Ошибка при логировании отладочной информации: {debug_err}")
            
        # Повторно выбрасываем оригинальную ошибку
        raise

def forecast(predictor: TimeSeriesPredictor, ts_df, known_covariates=None):
    """
    Выполняет прогнозирование с помощью обученного предиктора.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученный TimeSeriesPredictor.
    ts_df : TimeSeriesDataFrame
        Данные для прогнозирования в формате TimeSeriesDataFrame.
    known_covariates : TimeSeriesDataFrame, опционально
        Известные ковариаты для прогнозирования.
    
    Returns:
    --------
    TimeSeriesDataFrame
        Результаты прогнозирования.
    """
    logging.info("Вызов predictor.predict()...")
    
    try:
        # Проверка совместимости частот
        if hasattr(predictor, 'freq') and hasattr(ts_df, 'freq'):
            if predictor.freq != ts_df.freq:
                logging.warning(f"Частота предиктора ({predictor.freq}) не совпадает с частотой данных ({ts_df.freq})")
                logging.info(f"Конвертируем данные к частоте предиктора {predictor.freq}")
                ts_df = ts_df.convert_frequency(freq=predictor.freq)
        
        # Проверка горизонта прогнозирования
        if hasattr(predictor, 'prediction_length'):
            logging.info(f"Горизонт прогнозирования: {predictor.prediction_length}")
        
        # Выполняем прогнозирование
        preds = predictor.predict(ts_df, known_covariates=known_covariates)
        logging.info(f"Прогнозирование завершено. Получено {len(preds)} рядов.")
        
        return preds
    except Exception as e:
        logging.error(f"Ошибка при прогнозировании: {e}")
        raise

def get_model_performance(predictor: TimeSeriesPredictor) -> Dict[str, Any]:
    """
    Извлекает метрики производительности моделей из предиктора.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученный TimeSeriesPredictor.
    
    Returns:
    --------
    Dict[str, Any]
        Словарь с метриками производительности моделей.
    """
    try:
        if not hasattr(predictor, 'leaderboard') or not callable(getattr(predictor, 'leaderboard', None)):
            return {'error': 'Информация о производительности моделей недоступна'}
        
        leaderboard = predictor.leaderboard()
        
        # Добавляем веса ансамбля, если доступны
        ensemble_weights = {}
        
        # Улучшенный поиск информации о весах ансамбля
        try:
            # Проверяем если у нас есть модель WeightedEnsemble в лидерборде
            if 'WeightedEnsemble' in leaderboard.index:
                # Пытаемся получить модель ансамбля разными способами
                if hasattr(predictor, '_trainer') and hasattr(predictor._trainer, '_get_best_model'):
                    model = predictor._trainer._get_best_model()
                    if hasattr(model, 'weights') and model.weights:
                        logging.info("Найдены веса ансамбля через _get_best_model()")
                        ensemble_weights = {str(model_name): float(weight) for model_name, weight in model.weights.items()}
                
                # Альтернативный метод получения моделей и весов из лидерборда
                if not ensemble_weights and hasattr(predictor, 'model_best'):
                    model_name = predictor.model_best
                    if model_name and 'WeightedEnsemble' in model_name:
                        try:
                            # Прямой доступ к модели
                            model = predictor._trainer.load_model(model_name)
                            if hasattr(model, 'weights') and model.weights:
                                logging.info(f"Найдены веса ансамбля через model_best: {model_name}")
                                ensemble_weights = {str(model_name): float(weight) for model_name, weight in model.weights.items()}
                        except Exception as e:
                            logging.warning(f"Не удалось получить веса ансамбля через model_best: {e}")
                
                # Если все еще не нашли веса, пробуем прямой доступ к модели WeightedEnsemble
                if not ensemble_weights:
                    for model_name in leaderboard.index:
                        if 'WeightedEnsemble' in model_name:
                            try:
                                model = predictor._trainer.load_model(model_name)
                                if hasattr(model, 'weights') and model.weights:
                                    logging.info(f"Найдены веса ансамбля через прямой доступ: {model_name}")
                                    ensemble_weights = {str(model_name): float(weight) for model_name, weight in model.weights.items()}
                                    break
                            except Exception as e:
                                logging.warning(f"Не удалось получить веса ансамбля через прямой доступ к {model_name}: {e}")
        except Exception as e:
            logging.warning(f"Не удалось извлечь веса ансамбля: {e}")
        
        # Преобразуем DataFrame в словарь для сериализации в JSON
        leaderboard_dict = {}
        for model_name in leaderboard.index:
            leaderboard_dict[model_name] = {
                col: float(leaderboard.loc[model_name, col]) 
                if isinstance(leaderboard.loc[model_name, col], (int, float, np.number)) 
                else str(leaderboard.loc[model_name, col])
                for col in leaderboard.columns
            }
        
        result = {'leaderboard': leaderboard_dict}
        
        # Добавляем информацию о весах ансамбля, если нашли
        if ensemble_weights:
            result['ensemble_weights'] = ensemble_weights
            logging.info(f"Извлечены веса ансамбля: {ensemble_weights}")
        
        return result
    except Exception as e:
        logging.error(f"Ошибка при получении метрик производительности: {e}")
        return {'error': str(e)}

def convert_predictions_to_dataframe(predictions: TimeSeriesDataFrame) -> pd.DataFrame:
    """
    Преобразует результаты прогнозирования из TimeSeriesDataFrame в обычный DataFrame.
    
    Parameters:
    -----------
    predictions : TimeSeriesDataFrame
        Результаты прогнозирования.
    
    Returns:
    --------
    pandas.DataFrame
        Обычный DataFrame с результатами прогнозирования.
    """
    try:
        # Проверяем, является ли объект TimeSeriesDataFrame
        if not isinstance(predictions, pd.DataFrame):
            raise ValueError("Неверный тип данных для преобразования")
        
        # Копируем данные и сбрасываем индекс
        if hasattr(predictions, 'reset_index'):
            df = predictions.reset_index()
        else:
            df = predictions.copy()
        
        return df
    except Exception as e:
        logging.error(f"Ошибка при преобразовании прогнозов в DataFrame: {e}")
        raise

def train_model(
    train_data: TimeSeriesDataFrame,
    hyperparameters: Optional[Union[Dict, str]] = None,
    time_limit: Optional[int] = None,
    preset: Optional[str] = None,
    model_path: Optional[str] = None,
    eval_metric: Optional[str] = None,
    prediction_length: Optional[int] = None,
    freq: Optional[str] = None
) -> Tuple[str, TimeSeriesPredictor]:
    """
    Обучает модель временных рядов.
    
    Parameters:
    -----------
    train_data : TimeSeriesDataFrame
        Данные для обучения
    hyperparameters : Dict или str, опционально
        Гиперпараметры модели. Может быть словарем или строкой "default" для использования всех моделей
    time_limit : int, опционально
        Ограничение времени обучения в секундах
    preset : str, опционально
        Предустановка для обучения. Возможные значения: 'best_quality', 'high_quality', 'good_quality', 'medium_quality', 'fast_training'.
    model_path : str, опционально
        Путь для сохранения модели
    eval_metric : str, опционально
        Метрика для оценки качества модели
    prediction_length : int, опционально
        Длина прогноза
    freq : str, опционально
        Частота временного ряда для явной передачи в TimeSeriesPredictor
        
    Returns:
    --------
    Tuple[str, TimeSeriesPredictor]
        Кортеж (путь к сохраненной модели, обученный предиктор)
    """
    try:
        # Проверяем, является ли preset Chronos/Bolt моделью, которая требует skip_model_selection=True
        is_skip_model_preset = False
        
        if preset:
            # Для Bolt/Chronos моделей проверяем, указан ли локальный путь или нужно загрузить локально
            if isinstance(preset, str) and (preset.startswith("bolt_") or preset.startswith("chronos")):
                logging.info(f"Обнаружена Chronos/Bolt модель: {preset}")
                
                # Устанавливаем флаг для специальной обработки
                is_skip_model_preset = True
                
                # Проверяем, существует ли локальная копия модели или это путь к модели
                if not os.path.exists(preset):
                    # Проверяем наличие локальной модели или загружаем её
                    preset = ensure_local_chronos_model(preset)
        
        # Если путь не указан, создаем временный
        if model_path is None:
            model_path = os.path.join(tempfile.gettempdir(), f"autogluon_ts_model_{int(time.time())}")
            logging.info(f"Модель будет сохранена во временную директорию: {model_path}")
        
        # Создаем директорию для модели, если её нет
        os.makedirs(model_path, exist_ok=True)
        
        # Устанавливаем метрику по умолчанию, если не указана
        if eval_metric is None:
            eval_metric = "RMSE"
        
        # Создаем TimeSeriesPredictor с настройками
        logging.info(f"Создание TimeSeriesPredictor с метрикой {eval_metric}")
        
        # Определяем квантили для предсказания
        quantile_levels = None
        if eval_metric in ["Quantile", "MAPE", "MASE"]:
            quantile_levels = [0.1, 0.5, 0.9]
        
        # Создаем предиктор
        predictor = TimeSeriesPredictor(
            prediction_length=prediction_length,
            path=model_path,
            eval_metric=eval_metric,
            quantile_levels=quantile_levels,
            freq=freq
        )
        
        # Проверяем, если hyperparameters="default" для использования всех моделей
        if hyperparameters == "default":
            logging.info("Используется hyperparameters='default' для включения всех моделей")
            # В этом случае используем preset и не передаем hyperparameters
            predictor.fit(
                train_data=train_data,
                time_limit=time_limit,
                presets=preset if preset else "medium_quality"
            )
        # Подбираем соответствующий метод обучения в зависимости от переданных параметров
        elif is_skip_model_preset:
            # Для Chronos/Bolt моделей, добавляем настройки для сохранения всех моделей в лидерборде
            # Если мы хотим включать другие модели помимо Chronos/Bolt для сравнения в лидерборде
            if hyperparameters and len(hyperparameters) > 0:
                logging.info(f"Обучение с использованием preset={preset} и дополнительными моделями для сравнения")
                # Создаем специальный гиперпараметр для Chronos с указанием конкретной модели
                # но при этом сохраняем другие модели для сравнения в лидерборде
                special_hyperparams = hyperparameters.copy()
                # Добавляем Chronos с выбранным preset или локальным путём
                special_hyperparams['Chronos'] = {'model_path': preset}
                predictor.fit(
                    train_data=train_data, 
                    time_limit=time_limit, 
                    hyperparameters=special_hyperparams,
                    skip_model_selection=False  # Явно указываем, чтобы обучить все модели
                )
            else:
                # Если нет дополнительных моделей, обучаем только Chronos/Bolt
                logging.info(f"Обучение с использованием preset={preset} без дополнительных моделей")
                if isinstance(preset, str) and os.path.exists(preset):
                    # Если preset - это путь к локальной модели
                    predictor.fit(
                        train_data=train_data, 
                        time_limit=time_limit, 
                        hyperparameters={'Chronos': {'model_path': preset}},
                        skip_model_selection=True
                    )
                else:
                    # Иначе используем preset как есть
                    predictor.fit(train_data=train_data, time_limit=time_limit, presets=preset)
        elif hyperparameters is None:
            # Если модели не указаны, обучаем со стандартными параметрами preset
            logging.info(f"Обучение с использованием preset={preset} без явного указания моделей")
            predictor.fit(train_data=train_data, time_limit=time_limit, presets=preset)
        else:
            # Если указан пустой словарь hyperparameters или "* (все)", используем все доступные модели
            if not hyperparameters:
                logging.info(f"Используем все доступные модели с preset={preset}")
                # Создаем словарь со всеми доступными моделями
                all_models = {model: {} for model in get_valid_models()}
                predictor.fit(train_data=train_data, time_limit=time_limit, hyperparameters=all_models, presets=preset)
            else:
                # Иначе используем указанные модели
                logging.info(f"Обучение с указанными моделями и preset={preset}")
                predictor.fit(train_data=train_data, time_limit=time_limit, hyperparameters=hyperparameters, presets=preset)
        
        logging.info("Обучение модели успешно завершено")
        
        # Возвращаем путь к модели и сам предиктор
        return (model_path, predictor)
    except Exception as e:
        logging.error(f"Ошибка при обучении модели: {e}")
        raise

def filter_valid_models(hyperparameters: Dict) -> Dict:
    """
    Фильтрует список моделей, оставляя только валидные модели.
    
    Parameters:
    -----------
    hyperparameters : Dict
        Словарь с гиперпараметрами моделей
        
    Returns:
    --------
    Dict
        Словарь с гиперпараметрами только валидных моделей
    """
    if hyperparameters is None:
        return None
    
    valid_models = get_valid_models()
    
    # Фильтруем модели, оставляя только валидные
    filtered_params = {}
    
    for model_name, params in hyperparameters.items():
        # Если это специальное значение "* (все)", возвращаем пустой словарь
        # что будет интерпретировано как "использовать все модели"
        if model_name == "* (все)":
            return {}
        
        if model_name in valid_models:
            filtered_params[model_name] = params
        else:
            logging.warning(f"Модель '{model_name}' не поддерживается и будет пропущена")
    
    return filtered_params


def get_valid_models() -> list:
    """
    Возвращает список валидных моделей.
    
    Returns:
    --------
    list
        Список названий поддерживаемых моделей
    """
    return [
        'ADIDA', 'ARIMA', 'AutoARIMA', 'AutoCES', 'AutoETS', 'Average', 
        'Chronos', 'Croston', 'CrostonSBA', 'DLinear', 'DeepAR', 
        'DirectTabular', 'DynamicOptimizedTheta', 'ETS', 'IMAPA', 
        'NPTS', 'Naive', 'PatchTST', 'RecursiveTabular', 'SeasonalAverage', 
        'SeasonalNaive', 'SimpleFeedForward', 'TemporalFusionTransformer', 
        'Theta', 'TiDE', 'WaveNet', 'Zero'
    ]

def extract_model_metrics(predictor: TimeSeriesPredictor, test_data=None, predictions=None) -> Dict[str, Any]:
    """
    Извлекает и форматирует метрики модели из обученного предиктора.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученный TimeSeriesPredictor
    test_data : TimeSeriesDataFrame, опционально
        Тестовые данные для оценки моделей
    predictions : TimeSeriesDataFrame, опционально
        Предсказания моделей на тестовых данных
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с метриками производительности и информацией о моделях
    """
    try:
        metrics = {}
        
        # Базовая информация о модели
        model_info = {
            "prediction_length": predictor.prediction_length,
            "freq": str(predictor.freq) if hasattr(predictor, 'freq') else "unknown",
            "eval_metric": predictor.eval_metric if hasattr(predictor, 'eval_metric') else "unknown",
            "quantile_levels": predictor.quantile_levels if hasattr(predictor, 'quantile_levels') else [0.1, 0.5, 0.9],
            "model_count": len(predictor.model_names()) if hasattr(predictor, 'model_names') and callable(predictor.model_names) else 0
        }
        
        # Информация о всех моделях в предикторе
        if hasattr(predictor, 'model_names') and callable(predictor.model_names):
            try:
                model_names = predictor.model_names()
                model_info["models"] = list(model_names)
                logging.info(f"Обученные модели: {model_names}")
            except Exception as e:
                logging.warning(f"Не удалось получить список моделей: {e}")
                model_info["models"] = []
        
        metrics["model_info"] = model_info
        
        # Получаем таблицу лидеров
        if hasattr(predictor, 'leaderboard') and callable(predictor.leaderboard):
            try:
                # Если есть тестовые данные и предсказания, используем их для получения полной таблицы лидеров
                if test_data is not None and predictions is not None:
                    logging.info("Получение таблицы лидеров с тестовыми данными и предсказаниями")
                    leaderboard = predictor.leaderboard(data=test_data, predictions=predictions, extra_info=True)
                else:
                    # Пробуем получить leaderboard стандартным способом
                    logging.info("Получение базовой таблицы лидеров без тестовых данных")
                    leaderboard = predictor.leaderboard(extra_info=True)
            except TypeError as e:
                if "missing 1 required positional argument: 'predictions'" in str(e):
                    # Если требуется predictions, значит у нас нет их пока - возвращаем базовую информацию
                    logging.warning("Не удалось получить полную таблицу лидеров: требуются predictions. "
                                   "Будет возвращена только базовая информация о модели.")
                    metrics["note"] = "Для получения полных метрик необходимо сначала выполнить прогноз"
                    return metrics
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise e
            except Exception as err:
                # Перехватываем ошибки, связанные с изменениями в API автоглюона
                logging.error(f"Ошибка при извлечении метрик модели: {err}")
                metrics["error"] = str(err)
                return metrics
        
        # Получаем информацию о составе ансамбля, если доступна
        try:
            if hasattr(predictor, '_trainer') and hasattr(predictor._trainer, '_get_best_model'):
                model = predictor._trainer._get_best_model()
                if hasattr(model, 'weights'):
                    weights = model.weights
                    ensemble_weights = {
                        model_name: float(weight) for model_name, weight in weights.items()
                    }
                    metrics["ensemble_weights"] = ensemble_weights
        except Exception as ensemble_err:
            logging.warning(f"Не удалось извлечь веса ансамбля: {ensemble_err}")
        
        # Получаем информацию о гиперпараметрах всех моделей
        try:
            if hasattr(predictor, 'get_info') and callable(predictor.get_info):
                models_info = predictor.get_info()
                if isinstance(models_info, dict):
                    # Фильтруем и форматируем информацию
                    hyperparams = {}
                    for model_name, info in models_info.items():
                        if isinstance(info, dict) and 'hyperparameters' in info:
                            # Берем только гиперпараметры
                            hyperparams[model_name] = info['hyperparameters']
                    
                    if hyperparams:
                        metrics["models_hyperparameters"] = hyperparams
        except Exception as hp_err:
            logging.warning(f"Не удалось извлечь гиперпараметры моделей: {hp_err}")
        
        # Если смогли получить leaderboard, обрабатываем его
        # Преобразуем DataFrame в словарь для сериализации в JSON
        leaderboard_dict = {}
        for model_name in leaderboard.index:
            leaderboard_dict[model_name] = {
                col: float(leaderboard.loc[model_name, col]) 
                if isinstance(leaderboard.loc[model_name, col], (int, float, np.number)) 
                else str(leaderboard.loc[model_name, col])
                for col in leaderboard.columns
            }
        
        metrics["leaderboard"] = leaderboard_dict
        
        # Получаем лучшую модель и метрику
        best_model = leaderboard.index[0]
        best_score = float(leaderboard.iloc[0][predictor.eval_metric])
        metrics["best_model"] = best_model
        metrics["best_score"] = best_score
        
        # Добавляем метрику и направление оптимизации (меньше/больше - лучше)
        metrics["eval_metric"] = predictor.eval_metric
        metrics["higher_is_better"] = predictor.higher_is_better
        
        return metrics
        
    except Exception as e:
        logging.error(f"Ошибка при извлечении метрик модели: {e}")
        return {"error": str(e), "model_info": {
            "prediction_length": predictor.prediction_length if hasattr(predictor, 'prediction_length') else None,
            "freq": str(predictor.freq) if hasattr(predictor, 'freq') else "unknown",
            "eval_metric": predictor.eval_metric if hasattr(predictor, 'eval_metric') else "unknown"
        }}

# Константы для локальных путей к моделям Chronos/Bolt
CHRONOS_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "chronos")

def ensure_local_chronos_model(model_name: str) -> str:
    """
    Проверяет наличие локальной копии модели Chronos/Bolt и загружает её при необходимости.
    
    Parameters:
    -----------
    model_name : str
        Название модели (например, 'bolt_small', 'chronos_base')
        
    Returns:
    --------
    str
        Путь к локальной модели
    """
    # Преобразуем названия пресетов в соответствующие HuggingFace репозитории
    model_mapping = {
        "bolt_tiny": "autogluon/chronos-bolt-tiny",
        "bolt_mini": "autogluon/chronos-bolt-mini",
        "bolt_small": "autogluon/chronos-bolt-small",
        "bolt_base": "autogluon/chronos-bolt-base",
        "chronos_tiny": "autogluon/chronos-t5-tiny",
        "chronos_mini": "autogluon/chronos-t5-mini",
        "chronos_small": "autogluon/chronos-t5-small",
        "chronos_base": "autogluon/chronos-t5-base",
        "chronos_large": "autogluon/chronos-t5-large",
        "chronos": "autogluon/chronos-t5-base",  # По умолчанию используем base версию
    }
    
    # Получаем HuggingFace repo_id для данной модели
    repo_id = model_mapping.get(model_name, f"autogluon/{model_name.replace('_', '-')}")
    
    # Создаем путь, куда будет загружена модель
    local_model_dir = os.path.join(CHRONOS_MODELS_DIR, model_name.replace("_", "/"))
    os.makedirs(os.path.dirname(local_model_dir), exist_ok=True)
    
    # Проверяем, существует ли локальная модель
    config_file = os.path.join(local_model_dir, "config.json")
    if os.path.exists(config_file):
        logging.info(f"Используем локальную копию модели {model_name} из {local_model_dir}")
        return local_model_dir
    
    # Если нет, скачиваем модель с HuggingFace
    try:
        logging.info(f"Локальная копия модели {model_name} не найдена, загружаем из {repo_id}")
        from huggingface_hub import snapshot_download
        
        # Скачиваем модель в указанную директорию
        model_dir = snapshot_download(
            repo_id=repo_id,
            local_dir=local_model_dir,
            local_dir_use_symlinks=False  # Не используем симлинки для совместимости с Windows
        )
        logging.info(f"Модель {model_name} успешно загружена в {model_dir}")
        return model_dir
    except Exception as e:
        logging.error(f"Ошибка при загрузке модели {model_name} из {repo_id}: {str(e)}")
        # В случае ошибки при загрузке, возвращаем путь, который будет использоваться как есть
        # AutoGluon сам попытается загрузить модель из интернета, если её нет локально
        return model_name

