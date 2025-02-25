# src/config.py
import os

CONFIG = {
    # Пути к файлам и директориям
    "MODEL_DIR": "AutogluonModels/TimeSeriesModel",
    "MODEL_INFO_FILE": "model_info.json",
    "LOG_FILE": "logs/app.log",
    "CONFIG_PATH": "config/config.yaml",
    
    # Значения по умолчанию
    "DEFAULT_CHUNK_SIZE": 100000,
    "DEFAULT_PREDICTION_LENGTH": 10,
    "DEFAULT_TIME_LIMIT": 60,
    "DEFAULT_FREQ": "auto (угадать)",
    "DEFAULT_FILL_METHOD": "None",
    "DEFAULT_METRIC": "MASE (Mean absolute scaled error)",
    "DEFAULT_PRESET": "medium_quality",
    
    # Настройки UI
    "MAX_VISIBLE_ROWS": 1000,
    "MAX_PLOT_POINTS": 10000,
    "MAX_IDS_FOR_PLOT": 10,
    
    # Настройки производительности
    "MEMORY_THRESHOLD_GB": 1.5,
    "ENABLE_CHUNK_PROCESSING": True
}

def get_config(key, default=None):
    """Получить значение из конфигурации или вернуть значение по умолчанию"""
    return CONFIG.get(key, default)

def get_full_path(relative_path):
    """Получить полный путь к файлу относительно корня проекта"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)