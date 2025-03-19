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
    prediction_length: int,
    model_path: str = None,
    time_limit: int = 300,
    eval_metric: str = "RMSE",
    hyperparameters: Optional[Dict] = None,
    preset: str = "medium_quality",
    freq: str = None,
):
    """
    Обучает модель прогнозирования временных рядов с использованием AutoGluon.
    
    Parameters:
    -----------
    train_data : TimeSeriesDataFrame
        DataFrame с данными временного ряда.
    prediction_length : int
        Длина прогноза (горизонт).
    model_path : str, опционально
        Путь для сохранения модели.
    time_limit : int, опционально
        Ограничение времени обучения в секундах.
    eval_metric : str, опционально
        Метрика оценки качества модели.
    hyperparameters : dict, опционально
        Словарь с гиперпараметрами моделей.
    preset : str, опционально
        Пресет для AutoGluon (medium_quality, high_quality, и т.д.).
    freq : str, опционально
        Частота данных ('D' для дневной, 'H' для часовой, и т.д.)
    
    Returns:
    --------
    Tuple[str, TimeSeriesPredictor]
        Путь к сохраненной модели и объект предиктора
    """
    logging.info(f"Начало обучения модели с горизонтом прогнозирования {prediction_length}")
    logging.info(f"Используемый пресет: {preset}, метрика: {eval_metric}")
    
    try:
        # Убедимся, что директория для модели существует
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Проверка параметров
        if prediction_length <= 0:
            raise ValueError(f"Некорректный горизонт прогнозирования: {prediction_length}")

        if not isinstance(train_data, TimeSeriesDataFrame):
            raise TypeError("train_data должен быть типа TimeSeriesDataFrame")
        
        # Если частота не указана, пытаемся получить её из данных
        if freq is None:
            freq = getattr(train_data, 'freq', 'D')  # По умолчанию 'D' если не удалось определить
            
        logging.info(f"Данные для обучения: {len(train_data)} рядов, частота: {freq}")
        
        # Определяем модели для обучения на основе hyperparameters
        models = {}
        if hyperparameters:
            models = {model: {} for model in hyperparameters.keys()}
            logging.info(f"Выбранные модели: {list(models.keys())}")
        
        # Инициализируем и обучаем предиктор
        predictor = TimeSeriesPredictor(
            prediction_length=prediction_length,
            path=model_path,
            eval_metric=eval_metric,
            target="target",
            freq=freq  # Добавляем параметр частоты
        )
        
        predictor.fit(
            train_data=train_data,
            time_limit=time_limit,
            hyperparameters=hyperparameters,
            presets=preset,
        )
        
        # Сохраняем модель (это происходит автоматически, но явно вызываем save для уверенности)
        try:
            predictor.save()
            logging.info(f"Модель успешно сохранена по пути: {model_path}")
        except Exception as save_error:
            logging.error(f"Ошибка при сохранении модели: {save_error}")
        
        return model_path, predictor
        
    except Exception as e:
        logging.error(f"Ошибка при обучении модели: {e}")
        raise RuntimeError(f"Не удалось обучить модель: {str(e)}")

def extract_model_metrics(predictor: TimeSeriesPredictor) -> Dict[str, Any]:
    """
    Извлекает и форматирует метрики модели из обученного предиктора.
    
    Parameters:
    -----------
    predictor : TimeSeriesPredictor
        Обученный предиктор AutoGluon
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с метриками производительности и информацией о моделях
    """
    try:
        metrics = {}
        
        # Получаем таблицу лидеров
        if hasattr(predictor, 'leaderboard') and callable(predictor.leaderboard):
            leaderboard = predictor.leaderboard()
            
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
        
        # Добавляем информацию о параметрах прогнозирования
        metrics["prediction_length"] = predictor.prediction_length
        metrics["freq"] = str(predictor.freq) if hasattr(predictor, 'freq') else "unknown"
        
        return metrics
        
    except Exception as e:
        logging.error(f"Ошибка при извлечении метрик модели: {e}")
        return {"error": str(e)}
