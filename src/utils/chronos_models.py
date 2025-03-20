"""
Модуль для работы с моделями Chronos.
Обеспечивает использование моделей Chronos-Bolt напрямую из Hugging Face без локального скачивания.
"""
import os
import logging
from pathlib import Path
import time
import warnings
from typing import Dict, Any, Tuple, Optional, Union

logger = logging.getLogger(__name__)

# Словарь соответствия названий моделей и их HF идентификаторов
CHRONOS_MODELS_MAPPING = {
    "bolt_tiny": "autogluon/chronos-bolt-tiny",
    "bolt_small": "autogluon/chronos-bolt-small", 
    "bolt_base": "autogluon/chronos-bolt-base",
    "chronos_tiny": "autogluon/chronos-tiny",
    "chronos_small": "autogluon/chronos-small",
    "chronos_base": "autogluon/chronos-base"
}

def get_base_dir() -> Path:
    """
    Возвращает базовый каталог приложения
    
    Returns:
        Path: Абсолютный путь к базовому каталогу приложения
    """
    base_dir = Path(os.environ.get("APP_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return base_dir

def get_model_path(model_name: str) -> str:
    """
    Получение пути к модели Chronos в формате Hugging Face
    
    Args:
        model_name (str): Имя модели Chronos
    
    Returns:
        str: Путь к модели в формате Hugging Face
        
    Raises:
        ValueError: Если модель не найдена в списке поддерживаемых
    """
    # Проверяем, является ли переданный путь уже HF путем
    if "/" in model_name:
        logger.info(f"Используется прямой путь к модели в HF: {model_name}")
        return model_name
    
    # Проверяем, есть ли модель в маппинге
    model_key = model_name.lower()
    if model_key in CHRONOS_MODELS_MAPPING:
        hf_path = CHRONOS_MODELS_MAPPING[model_key]
        logger.info(f"Найдено соответствие в маппинге: {model_key} -> {hf_path}")
        return hf_path
    
    # Если модель не найдена в маппинге, пробуем использовать её как репозиторий HF напрямую
    # Добавляем стандартный префикс, если это просто имя модели
    if "autogluon/" not in model_name:
        hf_path = f"autogluon/{model_name}"
        logger.info(f"Модель не найдена в маппинге, пробуем использовать с префиксом: {hf_path}")
        return hf_path
    
    return model_name

def modify_chronos_hyperparams(hyperparams: Dict[str, Any]) -> Dict[str, Any]:
    """
    Модифицирует гиперпараметры для использования моделей Chronos
    
    Args:
        hyperparams (Dict[str, Any]): Исходные гиперпараметры
    
    Returns:
        Dict[str, Any]: Модифицированные гиперпараметры
    """
    # Создаем копию гиперпараметров
    modified_params = hyperparams.copy()
    
    # Если явно указаны параметры для модели Chronos
    if "Chronos" in modified_params:
        chronos_params = modified_params["Chronos"].copy()
        
        # Если указан путь к модели
        if "model_path" in chronos_params:
            model_name = chronos_params["model_path"]
            
            try:
                # Получаем HF путь к модели
                hf_path = get_model_path(model_name)
                
                # Заменяем путь на HF путь
                chronos_params["model_path"] = hf_path
                modified_params["Chronos"] = chronos_params
                
                # Логируем изменения
                logger.info(f"Используем модель из Hugging Face: {hf_path}")
                
            except Exception as e:
                logger.warning(f"Ошибка при определении пути к модели {model_name}: {str(e)}")
    
    return modified_params

def create_chronos_predictor(prediction_length: int, train_data=None, model_name: str = "bolt_small", 
                           time_limit: int = 300, hyperparams: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
    """
    Создаёт предиктор на основе Chronos модели
    
    Args:
        prediction_length (int): Горизонт прогнозирования
        train_data: Данные для обучения (опционально)
        model_name (str): Имя модели Chronos
        time_limit (int): Ограничение времени обучения в секундах
        hyperparams (Dict[str, Any]): Гиперпараметры моделей (опционально)
        **kwargs: Дополнительные параметры для предиктора
    
    Returns:
        TimeSeriesPredictor: Предиктор на основе Chronos модели
        
    Raises:
        ValueError: Если модель не может быть загружена
    """
    start_time = time.time()
    logger.info(f"Создание предиктора Chronos {model_name}, horizont={prediction_length}")
    
    # Пытаемся импортировать TimeSeriesPredictor
    try:
        from autogluon.timeseries import TimeSeriesPredictor
    except ImportError as e:
        error_msg = f"Не удалось импортировать TimeSeriesPredictor: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Получаем HF путь к модели
    hf_model_path = get_model_path(model_name)
    
    # Формируем гиперпараметры
    if hyperparams is None:
        hyperparams = {
            "Chronos": {"model_path": hf_model_path}
        }
    else:
        # Если уже есть секция Chronos, обновляем путь к модели
        if "Chronos" in hyperparams:
            hyperparams["Chronos"]["model_path"] = hf_model_path
        else:
            # Иначе создаем новую секцию
            hyperparams["Chronos"] = {"model_path": hf_model_path}
    
    # Создаем предиктор с указанными параметрами
    predictor = TimeSeriesPredictor(
        prediction_length=prediction_length,
        **kwargs
    )
    
    # Если переданы данные для обучения, обучаем предиктор
    if train_data is not None:
        logger.info(f"Обучение предиктора на данных с {len(train_data)} рядами")
        
        try:
            predictor.fit(
                train_data=train_data,
                hyperparameters=hyperparams,
                time_limit=time_limit
            )
            
            # Логируем информацию о времени обучения
            elapsed_time = time.time() - start_time
            logger.info(f"Предиктор успешно обучен за {elapsed_time:.2f} сек.")
            
        except Exception as e:
            logger.error(f"Ошибка при обучении предиктора: {str(e)}")
            raise ValueError(f"Ошибка при обучении предиктора: {str(e)}")
    
    return predictor

def check_model_availability(model_name: str) -> Dict[str, Any]:
    """
    Проверяет доступность модели Chronos по указанному имени или пути
    
    Args:
        model_name (str): Имя или путь к модели
    
    Returns:
        Dict[str, Any]: Словарь с информацией о доступности модели
    """
    result = {
        "model_name": model_name,
        "available": False,
        "local_path": None,
        "error": None,
        "log": []
    }
    
    try:
        hf_path = get_model_path(model_name)
        
        result["available"] = True
        result["local_path"] = hf_path
        result["log"] = [f"Используем модель из Hugging Face: {hf_path}"]
        
    except Exception as e:
        result["error"] = str(e)
        
    return result

def example_usage():
    """
    Пример использования функционала модуля
    """
    logging.basicConfig(level=logging.INFO)
    
    # Пример 1: Получение пути к модели
    try:
        model_path = get_model_path("bolt_tiny")
        print(f"Путь к модели: {model_path}")
    except ValueError as e:
        print(f"Ошибка: {e}")
    
    # Пример 2: Модификация гиперпараметров
    hyperparams = {
        "Chronos": {"model_path": "autogluon/chronos-bolt-tiny"}
    }
    modified = modify_chronos_hyperparams(hyperparams)
    print(f"Исходные параметры: {hyperparams}")
    print(f"Модифицированные параметры: {modified}")
    
    # Пример 3: Создание предиктора (без обучения)
    try:
        predictor = create_chronos_predictor(prediction_length=24)
        print(f"Предиктор создан: {predictor}")
    except Exception as e:
        print(f"Ошибка при создании предиктора: {e}")

# Если модуль запущен напрямую, показываем пример использования
if __name__ == "__main__":
    example_usage()