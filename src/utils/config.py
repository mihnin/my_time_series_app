"""
Централизованная конфигурация приложения
"""

import os
import logging
from pathlib import Path

# Логгер
logger = logging.getLogger(__name__)

# Базовые пути
APP_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = APP_ROOT / "data"
MODELS_DIR = APP_ROOT / "models"
LOGS_DIR = APP_ROOT / "logs"
TEMP_DIR = APP_ROOT / "temp"
CONFIG_DIR = APP_ROOT / "config"

# Директории данных
UPLOAD_DIR = DATA_DIR / "uploads"
TRAIN_DATA_DIR = DATA_DIR / "train"
TEST_DATA_DIR = DATA_DIR / "test"
PREDICTION_DIR = DATA_DIR / "predictions"
EXPORT_DIR = DATA_DIR / "exports"
VALIDATION_DIR = DATA_DIR / "validation"

# Директории моделей
AUTOGLUON_MODELS_DIR = MODELS_DIR / "AutogluonModels"
TIMESERIES_MODELS_DIR = AUTOGLUON_MODELS_DIR / "TimeSeriesModel"
ENSEMBLE_MODELS_DIR = MODELS_DIR / "ensembles"
LIGHTGBM_MODELS_DIR = MODELS_DIR / "lightgbm"
PROPHET_MODELS_DIR = MODELS_DIR / "prophet"
CHRONOS_MODELS_DIR = MODELS_DIR / "chronos"

# Директории для внешних моделей и ресурсов
EXTERNAL_MODELS_DIR = MODELS_DIR / "external"
HF_CACHE_DIR = MODELS_DIR / "hf_cache"

# Конфигурационные файлы
DEFAULT_CONFIG_FILE = CONFIG_DIR / "default_config.json"
USER_CONFIG_FILE = CONFIG_DIR / "user_config.json"
MODEL_METADATA_FILE = CONFIG_DIR / "model_metadata.json"
SAVE_STATE_FILE = CONFIG_DIR / "saved_state.json"

# Инициализация директорий
def init_directories():
    """
    Создаёт необходимые директории, если они не существуют
    """
    directories = [
        DATA_DIR, MODELS_DIR, LOGS_DIR, TEMP_DIR, CONFIG_DIR,
        UPLOAD_DIR, TRAIN_DATA_DIR, TEST_DATA_DIR, PREDICTION_DIR, EXPORT_DIR, VALIDATION_DIR,
        AUTOGLUON_MODELS_DIR, TIMESERIES_MODELS_DIR, ENSEMBLE_MODELS_DIR, 
        LIGHTGBM_MODELS_DIR, PROPHET_MODELS_DIR, CHRONOS_MODELS_DIR,
        EXTERNAL_MODELS_DIR, HF_CACHE_DIR
    ]
    
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Директория создана или существует: {directory}")
        except Exception as e:
            logger.error(f"Ошибка при создании директории {directory}: {e}")

# URLs и адреса внешних ресурсов
DEFAULT_HF_MODEL_REPO = "huggingface/time-series-transformer-tourism-monthly"
CHRONOS_MODELS_MAPPING = {
    "timeseries-transformer-base": "huggingface/time-series-transformer-tourism-monthly",
    "timeseries-transformer-tourism": "huggingface/time-series-transformer-tourism-monthly",
    "timeseries-transformer-electricity": "huggingface/time-series-transformer-electricity-hourly",
    "timeseries-transformer-traffic": "huggingface/time-series-transformer-traffic-hourly"
}

# Конфигурация Streamlit
STREAMLIT_THEME = {
    "primaryColor": "#5B68FF",
    "backgroundColor": "#FFF",
    "secondaryBackgroundColor": "#F0F2F6",
    "textColor": "#262730",
    "font": "sans-serif"
}

# Значения по умолчанию
DEFAULT_TIME_LIMIT = 300  # 5 минут на обучение
DEFAULT_PREDICTION_LENGTH = 24
DEFAULT_MODELS = ["DeepAR", "PatchTST", "TemporalFusionTransformer", "SimpleFeedForward"]
DEFAULT_FREQUENCY = "h"  # часовая (обновлено с 'H' на 'h' для совместимости с pandas 2.2.0)

# Параметры производительности
MAX_MEMORY_USAGE_GB = 4  # Максимальное ограничение по памяти, ГБ
MAX_THREADS = 4  # Максимальное количество потоков
DEFAULT_CHUNK_SIZE = 10000  # Размер чанка для обработки больших данных

# Настройки визуализации
MAX_VISUALIZE_POINTS = 5000  # Максимальное количество точек для визуализации
DEFAULT_PLOT_STYLE = "streamlit"  # Стиль графиков по умолчанию

# Настройки сохранения и загрузки
MAX_UPLOAD_SIZE_MB = 200  # Максимальный размер загружаемого файла
STREAMLIT_STATE_KEY = "app_state"  # Ключ для хранения состояния в Streamlit

# Настройки интеграций и API
HF_TOKEN_ENV_NAME = "HF_TOKEN"  # Имя переменной окружения для токена Hugging Face

# Функция для получения пути к модели
def get_model_path(model_id, model_type="autogluon"):
    """
    Возвращает путь к модели на основе её идентификатора и типа
    
    Аргументы:
        model_id (str): Идентификатор модели
        model_type (str): Тип модели (autogluon, lightgbm, prophet, chronos, ensemble)
        
    Возвращает:
        Path: Путь к директории или файлу модели
    """
    if model_type.lower() == "autogluon":
        return TIMESERIES_MODELS_DIR / model_id
    elif model_type.lower() == "lightgbm":
        return LIGHTGBM_MODELS_DIR / f"{model_id}.txt"
    elif model_type.lower() == "prophet":
        return PROPHET_MODELS_DIR / f"{model_id}.json"
    elif model_type.lower() == "chronos":
        return CHRONOS_MODELS_DIR / model_id
    elif model_type.lower() == "ensemble":
        return ENSEMBLE_MODELS_DIR / f"{model_id}.pkl"
    else:
        logger.warning(f"Неизвестный тип модели: {model_type}, используется путь по умолчанию")
        return MODELS_DIR / f"{model_type}" / model_id

# Инициализация при импорте
init_directories() 