# src/models/forecasting.py
import logging
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Union, Tuple
import os
from pathlib import Path

def make_timeseries_dataframe(df, static_features=None, freq='D'):
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
    
    Returns:
    --------
    TimeSeriesDataFrame
        TimeSeriesDataFrame для использования в AutoGluon.
    """
    try:
        # Проверка необходимых колонок
        required_cols = ["item_id", "timestamp", "target"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Отсутствует обязательная колонка: {col}")
        
        # Проверка типа данных для timestamp
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            logging.warning("Колонка timestamp не имеет тип datetime64. Преобразуем...")
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            
            # Проверяем успешность преобразования
            if df["timestamp"].isna().any():
                failed_values = df.loc[df["timestamp"].isna(), "timestamp"].head(5).tolist()
                logging.error(f"Не удалось преобразовать некоторые значения даты: {failed_values}")
                raise ValueError("Ошибка преобразования timestamp в datetime")
        
        # Проверка на дубликаты
        duplicate_pairs = df.duplicated(subset=["item_id", "timestamp"]).sum()
        if duplicate_pairs > 0:
            logging.warning(f"Найдены дубликаты в парах item_id-timestamp: {duplicate_pairs}. Удаляем...")
            df = df.drop_duplicates(subset=["item_id", "timestamp"])
        
        # Проверка на пропуски в целевой переменной
        num_missing = df["target"].isna().sum()
        if num_missing > 0:
            missing_percent = 100 * num_missing / len(df)
            logging.warning(f"В колонке target есть пропуски: {num_missing} ({missing_percent:.2f}%)")
            # Здесь можно добавить автоматическое заполнение пропусков, если нужно
        
        # Создаем TimeSeriesDataFrame
        ts_df = TimeSeriesDataFrame(df, static_features=static_features)
        
        # Устанавливаем частоту, если указана и не auto
        if freq and freq.lower() != 'auto':
            try:
                logging.info(f"Устанавливаем частоту {freq} для TimeSeriesDataFrame")
                ts_df = ts_df.convert_frequency(freq=freq)
            except Exception as freq_err:
                logging.warning(f"Не удалось установить частоту {freq}: {freq_err}")
                # Пытаемся определить частоту автоматически
                try:
                    inferred_freq = pd.infer_freq(
                        df.loc[df["item_id"] == df["item_id"].iloc[0]]["timestamp"]
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
            logging.error(f"Ошибка при отладочном логировании: {debug_err}")
        
        raise ValueError(f"Не удалось создать TimeSeriesDataFrame: {e}")

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
        if not hasattr(predictor, 'leaderboard') or predictor.leaderboard is None:
            return {'error': 'Информация о производительности моделей недоступна'}
        
        leaderboard = predictor.leaderboard()
        
        # Добавляем веса ансамбля, если доступны
        if hasattr(predictor, '_trainer') and predictor._trainer is not None:
            try:
                if hasattr(predictor._trainer, '_get_best_model') and hasattr(predictor._trainer._get_best_model(), 'weights'):
                    model = predictor._trainer._get_best_model()
                    if hasattr(model, 'weights'):
                        weights = model.weights
                        weighted_models = {}
                        for model_name, weight in weights.items():
                            weighted_models[model_name] = float(weight)
                        
                        return {
                            'leaderboard': leaderboard,
                            'ensemble_weights': weighted_models
                        }
            except Exception as e:
                logging.warning(f"Не удалось извлечь веса ансамбля: {e}")
        
        return {'leaderboard': leaderboard}
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
    hyperparameters: Optional[Dict] = None,
    time_limit: Optional[int] = None,
    preset: Optional[str] = None,
    model_path: Optional[str] = None,
    eval_metric: Optional[str] = None,
    prediction_length: Optional[int] = None
) -> TimeSeriesPredictor:
    """
    Обучает модель временных рядов.
    
    Parameters:
    -----------
    train_data : TimeSeriesDataFrame
        Данные для обучения
    hyperparameters : Dict, опционально
        Гиперпараметры модели
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
        
    Returns:
    --------
    TimeSeriesPredictor
        Обученный предиктор
    """
    try:
        # Настройка параметров обучения
        if time_limit is None:
            time_limit = 3600  # 1 час по умолчанию
        
        if preset is None:
            # Выбираем preset в зависимости от ограничения по времени
            if time_limit <= 300:  # <= 5 минут
                preset = 'fast_training'
            elif time_limit <= 1800:  # <= 30 минут
                preset = 'medium_quality'
            else:
                preset = 'high_quality'
        
        if eval_metric is None:
            eval_metric = "MASE"
        
        if prediction_length is None:
            prediction_length = 10
        
        # Валидируем и, при необходимости, корректируем список моделей для обучения
        if hyperparameters is not None:
            # Фильтруем список моделей от невалидных значений
            hyperparameters = filter_valid_models(hyperparameters)
            
            # Проверяем, если после фильтрации список пуст
            if not hyperparameters:
                logging.info("Список моделей после фильтрации оказался пустым. Будут использованы все доступные модели.")
                # Используем все доступные модели
                hyperparameters = {model: {} for model in get_valid_models()}
        
        # Логируем информацию о процессе обучения
        logging.info(f"Начинаем обучение модели с preset={preset}, time_limit={time_limit}с, eval_metric={eval_metric}")
        
        if hyperparameters is not None:
            model_count = len(hyperparameters)
            model_list = ", ".join(list(hyperparameters.keys()))
            logging.info(f"Будет обучено {model_count} моделей: {model_list}")
        else:
            logging.info("Будут обучены все модели из выбранного preset")
        
        # Настраиваем квантили для лучшей оценки неопределенности
        quantile_levels = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        
        # Создаем предиктор
        predictor = TimeSeriesPredictor(
            prediction_length=prediction_length,
            path=model_path,
            eval_metric=eval_metric,
            target="target",
            quantile_levels=quantile_levels
        )
        
        # Подбираем соответствующий метод обучения в зависимости от переданных параметров
        if hyperparameters is None:
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
        
        return predictor
    
    except Exception as e:
        logging.error(f"Ошибка при обучении модели: {e}")
        raise RuntimeError(f"Не удалось обучить модель: {str(e)}")


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
        'DeepAR', 'Transformer', 'PatchTST', 'TemporalFusionTransformer',
        'DLinear', 'NLinear', 'SeasNaive', 'Seasonal', 'ETS', 'AutoETS',
        'ARIMA', 'AutoARIMA', 'Theta', 'NPTS', 'RNN', 'CNN',
        'ADIDA', 'Croston', 'IMAPA', 'MLP', 'WaveNet',
        'SimpleFeedForward', 'MQCNN', 'AutoGluonTabular'
    ]

def extract_model_metrics(predictor: TimeSeriesPredictor, test_data=None, predictions=None) -> Dict[str, Any]:
    """
    Извлекает и форматирует метрики модели из обученного предиктора.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученный предиктор AutoGluon
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
            "model_count": len(predictor.get_model_names()) if hasattr(predictor, 'get_model_names') and callable(predictor.get_model_names) else 0
        }
        
        # Информация о всех моделях в предикторе
        if hasattr(predictor, 'get_model_names') and callable(predictor.get_model_names):
            try:
                model_names = predictor.get_model_names()
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
        
        return metrics
        
    except Exception as e:
        logging.error(f"Ошибка при извлечении метрик модели: {e}")
        return {"error": str(e), "model_info": {
            "prediction_length": predictor.prediction_length if hasattr(predictor, 'prediction_length') else None,
            "freq": str(predictor.freq) if hasattr(predictor, 'freq') else "unknown",
            "eval_metric": predictor.eval_metric if hasattr(predictor, 'eval_metric') else "unknown"
        }}
