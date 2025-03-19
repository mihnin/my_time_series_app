"""
Модуль для работы с моделями Chronos.
Обеспечивает использование локальных моделей Chronos-Bolt в корпоративной среде без доступа к Hugging Face.
"""
import os
import logging
from pathlib import Path
import time
import warnings

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

def get_local_model_path(model_name, use_bolt=False, allow_download=True):
    """
    Получение пути к локальной модели Chronos
    
    Аргументы:
        model_name (str): Имя или путь к модели Chronos
        use_bolt (bool): Использовать облегченную версию модели (bolt)
        allow_download (bool): Разрешить загрузку модели с Hugging Face
    
    Возвращает:
        str: Локальный путь к модели
        
    Вызывает:
        ValueError: Если модель не найдена или не может быть загружена
    """
    # Получаем директорию для моделей из конфигурации
    try:
        from src.utils.config import CHRONOS_MODELS_DIR, HF_CACHE_DIR
        models_dir = CHRONOS_MODELS_DIR
        hf_cache_dir = HF_CACHE_DIR
    except ImportError:
        # Если конфигурация не доступна, используем значения по умолчанию
        models_dir = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 "models", "chronos"))
        hf_cache_dir = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                 "models", "hf_cache"))
    
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
    
    # Определяем суффикс модели
    model_suffix = "-bolt" if use_bolt else ""
    
    # Проверяем разные варианты локальных путей
    local_paths = [
        # 1. Прямое имя модели в директории моделей
        os.path.join(models_dir, f"{model_name}{model_suffix}"),
        # 2. Имя модели с префиксом как поддиректория
        os.path.join(models_dir, model_name, f"{model_name}{model_suffix}"),
        # 3. Только имя модели как поддиректория
        os.path.join(models_dir, model_name),
        # 4. Путь к кэшу HF
        os.path.join(hf_cache_dir, model_name)
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
            from src.utils.config import CHRONOS_MODELS_MAPPING, DEFAULT_HF_MODEL_REPO
            
            # Преобразуем имя модели в имя репозитория HF, если оно есть в маппинге
            if model_name in CHRONOS_MODELS_MAPPING:
                repo_id = CHRONOS_MODELS_MAPPING[model_name]
                log_messages.append(f"Найдено соответствие в маппинге: {model_name} -> {repo_id}")
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
                local_model_path = os.path.join(models_dir, model_name)
                log_messages.append(f"Пытаемся загрузить модель из {repo_id} в {local_model_path}")
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Пытаемся загрузить модель
                    model = AutoModelForPrediction.from_pretrained(
                        repo_id,
                        cache_dir=hf_cache_dir,
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
    
    log_messages.append(f"ОШИБКА: {error_message}")
    full_log = "\n".join(log_messages)
    
    logging.error(full_log)
    raise ValueError(f"{error_message}\n\nДиагностика:\n{full_log}")

def modify_chronos_hyperparams(model_name, hyperparameters=None):
    """
    Модифицирует гиперпараметры для моделей Chronos
    
    Аргументы:
        model_name (str): Имя модели
        hyperparameters (dict): Словарь гиперпараметров
    
    Возвращает:
        dict: Обновленный словарь гиперпараметров
    """
    import logging
    
    if hyperparameters is None:
        hyperparameters = {}
    
    # Создаем глубокую копию словаря, чтобы не изменять оригинал
    import copy
    chronos_params = copy.deepcopy(hyperparameters)
    
    logging.info(f"Модификация гиперпараметров для модели Chronos: {model_name}")
    
    # Общие параметры для всех моделей Chronos
    chronos_params.update({
        'learning_rate': chronos_params.get('learning_rate', 1e-4),
        'num_epochs': chronos_params.get('num_epochs', 5),
        'batch_size': chronos_params.get('batch_size', 32),
        'use_gpu': chronos_params.get('use_gpu', True),
        'scaler_type': chronos_params.get('scaler_type', 'robust'),
    })
    
    # Специфичные параметры в зависимости от типа модели
    if model_name and 'timeseries-transformer' in model_name.lower():
        # Трансформеры обычно требуют особых настроек
        chronos_params.update({
            'patience': chronos_params.get('patience', 3),
            'gradient_clip_val': chronos_params.get('gradient_clip_val', 1.0),
            'weight_decay': chronos_params.get('weight_decay', 1e-5),
        })
    
    if model_name and 'bolt' in model_name.lower():
        # Облегченные модели Bolt требуют меньше ресурсов
        chronos_params.update({
            'batch_size': chronos_params.get('batch_size', 64),
            'use_gpu': chronos_params.get('use_gpu', False),  # По умолчанию используем CPU для bolt моделей
        })
    
    # Логируем обновленные параметры
    logging.info(f"Обновленные гиперпараметры для Chronos: {chronos_params}")
    
    return chronos_params

def create_chronos_predictor(model_name, use_bolt=False, allow_download=True, **kwargs):
    """
    Создаёт предиктор на основе Chronos модели
    
    Аргументы:
        model_name (str): Имя или путь к модели Chronos
        use_bolt (bool): Использовать облегченную версию модели (bolt)
        allow_download (bool): Разрешить загрузку модели с Hugging Face
        **kwargs: Дополнительные параметры для предиктора
    
    Возвращает:
        ChronosPredictor: Предиктор на основе Chronos модели
        
    Вызывает:
        ValueError: Если модель не найдена или не может быть загружена
    """
    # Получаем путь к локальной модели
    model_path, log = get_local_model_path(model_name, use_bolt, allow_download)
    
    # Логируем результат поиска модели
    logging.info(f"Создание предиктора на основе Chronos модели: {model_name} (путь: {model_path})")
    
    # Создаем предиктор
    from autogluon.timeseries.models.chronos.chronos import ChronosModel
    predictor = ChronosModel(
        model_path=model_path,
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
        model_name="bolt_base",
        use_bolt=True,
        allow_download=True,
        time_limit=60  # Ограничение времени в секундах
    )
    
    # Генерация прогнозов
    predictions = predictor.predict(df)
    return predictions