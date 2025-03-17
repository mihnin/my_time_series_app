"""
Модуль для работы с моделями Chronos.
Обеспечивает использование локальных моделей Chronos-Bolt в корпоративной среде без доступа к Hugging Face.
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Словарь соответствия названий моделей и их локальных путей
CHRONOS_MODELS_MAPPING = {
    "bolt_tiny": "chronos-bolt-tiny",
    "bolt_small": "chronos-bolt-small", 
    "bolt_base": "chronos-bolt-base",
    "autogluon/chronos-bolt-tiny": "chronos-bolt-tiny",
    "autogluon/chronos-bolt-small": "chronos-bolt-small",
    "autogluon/chronos-bolt-base": "chronos-bolt-base"
}

def get_base_dir():
    """Возвращает базовый каталог приложения"""
    return Path(os.environ.get("APP_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

def get_local_model_path(model_name):
    """
    Возвращает локальный путь к модели Chronos, если она доступна
    
    Аргументы:
        model_name (str): Имя модели (например, "bolt_tiny", "bolt_small", "bolt_base")
    
    Возвращает:
        str: Абсолютный путь к локальной модели или исходное имя модели
    """
    base_dir = get_base_dir()
    chronos_dir = base_dir / "autogluon"
    
    if model_name in CHRONOS_MODELS_MAPPING:
        model_dir = chronos_dir / CHRONOS_MODELS_MAPPING[model_name]
        if model_dir.exists():
            logger.info(f"Используется локальная модель Chronos: {model_dir}")
            return str(model_dir)
    
    logger.info(f"Локальная модель не найдена для {model_name}, будет использован Hugging Face")
    return model_name

def modify_chronos_hyperparams(hyperparams):
    """
    Модифицирует гиперпараметры для использования локальных моделей Chronos
    
    Аргументы:
        hyperparams (dict): Словарь гиперпараметров для TimeSeriesPredictor
    
    Возвращает:
        dict: Модифицированные гиперпараметры
    """
    if hyperparams is None:
        return hyperparams
        
    # Создаем копию для избежания изменения исходного словаря
    modified_hyperparams = hyperparams.copy()
    
    # Если указаны конфигурации для Chronos
    if "Chronos" in modified_hyperparams:
        chronos_configs = modified_hyperparams["Chronos"]
        
        # Если это список конфигураций
        if isinstance(chronos_configs, list):
            for i, config in enumerate(chronos_configs):
                if "model_path" in config:
                    modified_hyperparams["Chronos"][i]["model_path"] = get_local_model_path(config["model_path"])
        # Если это словарь (одна конфигурация)
        elif isinstance(chronos_configs, dict) and "model_path" in chronos_configs:
            modified_hyperparams["Chronos"]["model_path"] = get_local_model_path(chronos_configs["model_path"])
    
    return modified_hyperparams

def create_chronos_predictor(prediction_length, train_data, hyperparams=None, **kwargs):
    """
    Создает и обучает TimeSeriesPredictor с настроенным использованием локальных моделей Chronos
    
    Аргументы:
        prediction_length (int): Длина прогноза
        train_data (TimeSeriesDataFrame): Тренировочные данные
        hyperparams (dict, optional): Гиперпараметры
        **kwargs: Дополнительные аргументы для TimeSeriesPredictor.fit()
    
    Возвращает:
        TimeSeriesPredictor: Обученный предиктор
    """
    try:
        from autogluon.timeseries import TimeSeriesPredictor
    except ImportError:
        logger.error("Не удалось импортировать AutoGluon TimeSeriesPredictor. Убедитесь, что пакет установлен.")
        raise
    
    # Если гиперпараметры не указаны, используем Chronos-Bolt (Small) по умолчанию
    if hyperparams is None:
        hyperparams = {
            "Chronos": {"model_path": "bolt_small"}
        }
    
    # Модифицируем гиперпараметры для использования локальных моделей
    modified_hyperparams = modify_chronos_hyperparams(hyperparams)
    
    # Создаем и обучаем предиктор
    predictor = TimeSeriesPredictor(prediction_length=prediction_length)
    predictor.fit(
        train_data=train_data,
        hyperparameters=modified_hyperparams,
        **kwargs
    )
    
    return predictor

def example_usage():
    """Пример использования функционала"""
    from autogluon.timeseries import TimeSeriesDataFrame
    
    # Загрузка тренировочных данных
    df = TimeSeriesDataFrame.from_path("https://autogluon.s3.amazonaws.com/datasets/timeseries/m4_hourly/train.csv")
    
    # Создание и обучение предиктора с использованием локальной модели Chronos-Bolt
    predictor = create_chronos_predictor(
        prediction_length=48,
        train_data=df,
        hyperparams={
            "Chronos": {"model_path": "bolt_base"}  # Используем локальную модель bolt_base
        },
        time_limit=60  # Ограничение времени в секундах
    )
    
    # Генерация прогнозов
    predictions = predictor.predict(df)
    return predictions