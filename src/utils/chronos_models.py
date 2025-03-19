"""
Модуль для работы с моделями Chronos.
Обеспечивает использование локальных моделей Chronos-Bolt в корпоративной среде без доступа к Hugging Face.
"""
import os
import logging
from pathlib import Path
import time
import warnings
from typing import Dict, Any, Tuple, Optional, Union

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

def get_base_dir() -> Path:
    """
    Возвращает базовый каталог приложения
    
    Returns:
        Path: Абсолютный путь к базовому каталогу приложения
    """
    base_dir = Path(os.environ.get("APP_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    return base_dir

def get_local_model_path(model_name: str, use_bolt: bool = False, allow_download: bool = True) -> Tuple[str, str]:
    """
    Получение пути к локальной модели Chronos
    
    Args:
        model_name (str): Имя или путь к модели Chronos
        use_bolt (bool): Использовать облегченную версию модели (bolt)
        allow_download (bool): Разрешить загрузку модели с Hugging Face
    
    Returns:
        Tuple[str, str]: Локальный путь к модели и лог сообщений
        
    Raises:
        ValueError: Если модель не найдена или не может быть загружена
    """
    # Получаем директорию для моделей из конфигурации
    try:
        from src.utils.config import CHRONOS_MODELS_DIR, HF_CACHE_DIR
        models_dir = CHRONOS_MODELS_DIR
        hf_cache_dir = HF_CACHE_DIR
    except ImportError:
        # Если конфигурация не доступна, используем значения по умолчанию
        base_dir = get_base_dir()
        models_dir = base_dir / "models" / "chronos"
        hf_cache_dir = base_dir / "models" / "hf_cache"
    
    # Убеждаемся, что директории существуют
    models_dir.mkdir(parents=True, exist_ok=True)
    hf_cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Логгер для сбора диагностических сообщений
    log_messages = []
    log_messages.append(f"Поиск модели: {model_name}, bolt: {use_bolt}, allow_download: {allow_download}")
    log_messages.append(f"Директория моделей: {models_dir}")
    log_messages.append(f"Директория кэша HF: {hf_cache_dir}")
    
    # Конвертируем model_name в путь если это уже полный путь
    if os.path.exists(model_name):
        log_messages.append(f"Найден прямой путь к модели: {model_name}")
        return model_name, "\n".join(log_messages)
    
    # Проверяем, есть ли модель в маппинге
    model_key = model_name.lower()
    if model_key in CHRONOS_MODELS_MAPPING:
        mapped_name = CHRONOS_MODELS_MAPPING[model_key]
        log_messages.append(f"Найдено соответствие в маппинге: {model_key} -> {mapped_name}")
        model_name = mapped_name
    
    # Определяем суффикс модели
    model_suffix = "-bolt" if use_bolt else ""
    
    # Проверяем разные варианты локальных путей
    local_paths = [
        # 1. Полный путь к модели в папке autogluon
        os.path.join(str(get_base_dir()), "autogluon", model_name),
        # 2. Прямое имя модели в директории моделей
        os.path.join(str(models_dir), f"{model_name}{model_suffix}"),
        # 3. Имя модели с префиксом как поддиректория
        os.path.join(str(models_dir), model_name, f"{model_name}{model_suffix}"),
        # 4. Только имя модели как поддиректория
        os.path.join(str(models_dir), model_name),
        # 5. Путь к кэшу HF
        os.path.join(str(hf_cache_dir), model_name)
    ]
    
    # Ищем модель в возможных локальных путях
    for path in local_paths:
        if os.path.exists(path):
            log_messages.append(f"Найдена локальная модель по пути: {path}")
            return path, "\n".join(log_messages)
        else:
            log_messages.append(f"Путь не существует: {path}")
    
    # Если локальная модель не найдена, пробуем получить из репозитория HF
    if allow_download:
        log_messages.append("Локальная модель не найдена, попытка загрузки с Hugging Face...")
        
        # Пытаемся импортировать модуль для получения моделей из HF
        try:
            from src.utils.config import CHRONOS_MODELS_MAPPING as CONFIG_MAPPING
            from src.utils.config import DEFAULT_HF_MODEL_REPO
            
            # Преобразуем имя модели в имя репозитория HF, если оно есть в маппинге
            if model_name in CONFIG_MAPPING:
                repo_id = CONFIG_MAPPING[model_name]
                log_messages.append(f"Найдено соответствие в конфигурации: {model_name} -> {repo_id}")
            else:
                # Если модель не найдена в маппинге, используем её как репозиторий HF напрямую или используем дефолтный
                repo_id = model_name if "/" in model_name else DEFAULT_HF_MODEL_REPO
                log_messages.append(f"Используем как репозиторий HF или стандартный: {repo_id}")
            
            # Пытаемся загрузить модель из репозитория HF
            try:
                # Проверка наличия токена HF
                hf_token = os.environ.get("HF_TOKEN", None)
                if hf_token:
                    log_messages.append("Найден токен HF в переменных окружения")
                else:
                    log_messages.append("Токен HF не найден, загрузка в анонимном режиме")
                
                # Проверяем интернет-соединение
                import socket
                try:
                    socket.create_connection(("huggingface.co", 443), timeout=3)
                    log_messages.append("Соединение с huggingface.co доступно")
                except OSError:
                    error_msg = "Нет доступа к huggingface.co, проверьте подключение к интернету"
                    log_messages.append(error_msg)
                    raise ValueError(error_msg)
                
                # Пытаемся загрузить библиотеку transformers
                try:
                    import transformers
                    log_messages.append(f"Библиотека transformers загружена, версия: {transformers.__version__}")
                except ImportError:
                    error_msg = "Не удалось импортировать библиотеку transformers. Установите её: pip install transformers"
                    log_messages.append(error_msg)
                    raise ValueError(error_msg)
                
                # Загружаем модель с HF
                from transformers import AutoModelForPrediction
                
                # Определяем путь сохранения модели
                local_model_path = os.path.join(str(models_dir), model_name)
                log_messages.append(f"Пытаемся загрузить модель из {repo_id} в {local_model_path}")
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Пытаемся загрузить модель
                    model = AutoModelForPrediction.from_pretrained(
                        repo_id,
                        cache_dir=str(hf_cache_dir),
                        token=hf_token
                    )
                    log_messages.append(f"Модель успешно загружена из {repo_id}")
                    
                    # Сохраняем модель локально
                    model.save_pretrained(local_model_path)
                    log_messages.append(f"Модель сохранена локально в {local_model_path}")
                    
                    return local_model_path, "\n".join(log_messages)
                    
            except Exception as e:
                error_msg = f"Не удалось загрузить модель с Hugging Face: {str(e)}"
                log_messages.append(error_msg)
                raise ValueError(error_msg)
                
        except ImportError as e:
            error_msg = f"Не удалось импортировать необходимые модули для загрузки с HF: {str(e)}"
            log_messages.append(error_msg)
            raise ValueError(error_msg)
    else:
        log_messages.append("Загрузка с Hugging Face отключена параметром allow_download=False")
    
    # Если все попытки неудачны, возвращаем ошибку
    error_message = f"Модель '{model_name}' не найдена локально"
    error_message += " и не может быть загружена с Hugging Face" if allow_download else ""
    error_message += f". Попробуйте установить модель вручную в директорию: {models_dir}"
    
    log_messages.append(error_message)
    raise ValueError(error_message)

def modify_chronos_hyperparams(hyperparams: Dict[str, Any], allow_download: bool = True) -> Dict[str, Any]:
    """
    Модифицирует гиперпараметры для использования локальных моделей Chronos
    
    Args:
        hyperparams (Dict[str, Any]): Исходные гиперпараметры
        allow_download (bool): Разрешить загрузку модели с Hugging Face
    
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
            model_path = chronos_params["model_path"]
            
            try:
                # Получаем локальный путь к модели
                local_path, log_message = get_local_model_path(
                    model_path, 
                    use_bolt=model_path.endswith("bolt") or "bolt" in model_path.lower(),
                    allow_download=allow_download
                )
                
                # Заменяем путь на локальный
                chronos_params["model_path"] = local_path
                modified_params["Chronos"] = chronos_params
                
                # Логируем изменения
                logger.info(f"Заменен путь к модели: {model_path} -> {local_path}")
                logger.debug(log_message)
                
            except Exception as e:
                logger.warning(f"Не удалось заменить путь к модели {model_path}: {str(e)}")
                # В случае ошибки оставляем оригинальный путь
    
    return modified_params

def create_chronos_predictor(prediction_length: int, train_data=None, model_name: str = "bolt_small", 
                           use_bolt: bool = False, allow_download: bool = True, time_limit: int = 300,
                           hyperparams: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
    """
    Создаёт предиктор на основе Chronos модели
    
    Args:
        prediction_length (int): Горизонт прогнозирования
        train_data: Данные для обучения (опционально)
        model_name (str): Имя или путь к модели Chronos
        use_bolt (bool): Использовать облегченную версию модели (bolt)
        allow_download (bool): Разрешить загрузку модели с Hugging Face
        time_limit (int): Ограничение времени обучения в секундах
        hyperparams (Dict[str, Any]): Гиперпараметры моделей (опционально)
        **kwargs: Дополнительные параметры для предиктора
    
    Returns:
        TimeSeriesPredictor: Предиктор на основе Chronos модели
        
    Raises:
        ValueError: Если модель не найдена или не может быть загружена
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
    
    # Получаем локальный путь к модели
    try:
        local_model_path, log_message = get_local_model_path(
            model_name, 
            use_bolt=use_bolt,
            allow_download=allow_download
        )
        logger.debug(log_message)
    except Exception as e:
        logger.error(f"Ошибка при получении пути к модели {model_name}: {str(e)}")
        raise ValueError(f"Не удалось получить путь к модели: {str(e)}")
    
    # Формируем гиперпараметры
    if hyperparams is None:
        hyperparams = {
            "Chronos": {"model_path": local_model_path}
        }
    else:
        # Если уже есть секция Chronos, обновляем путь к модели
        if "Chronos" in hyperparams:
            hyperparams["Chronos"]["model_path"] = local_model_path
        else:
            # Иначе создаем новую секцию
            hyperparams["Chronos"] = {"model_path": local_model_path}
    
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
    else:
        logger.info("Данные для обучения не предоставлены, создан необученный предиктор")
    
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
        local_path, log_message = get_local_model_path(
            model_name, 
            allow_download=False  # Не пытаемся скачать модель
        )
        
        result["available"] = True
        result["local_path"] = local_path
        result["log"] = log_message.split("\n")
        
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
        model_path, log = get_local_model_path("bolt_tiny")
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