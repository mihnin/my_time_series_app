import logging
import os
from autogluon.timeseries import TimeSeriesPredictor

from pathlib import Path
import datetime

LOG_PATH = Path("logs") / f"train_{datetime.datetime.now().strftime('%Y%m%d')}.log"
MODEL_PATH = Path("saved_models") / datetime.datetime.now().strftime("%Y%m%d_%H%M")

def setup_logger():
    """
    Настраивает логгер для всего приложения.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Создаем директорию для логов если не существует
        os.makedirs(LOG_PATH.parent, exist_ok=True)
        file_handler = logging.FileHandler(LOG_PATH)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logger.addHandler(console_handler)

    logging.info("Инициализация логгера завершена")

def save_model(predictor):
    """
    Сохраняет обученную модель (predictor) в MODEL_PATH.
    """
    logging.info("Старт сохранения модели...")
    os.makedirs(MODEL_PATH, exist_ok=True)
    predictor.save(MODEL_PATH)
    logging.info(f"Модель успешно сохранена в {MODEL_PATH}")

def load_model():
    """
    Загружает модель из MODEL_PATH, если она существует.
    """
    logging.info("Попытка загрузки модели...")
    if not os.path.exists(MODEL_PATH):
        logging.error("Модель для загрузки не найдена")
        raise FileNotFoundError("Модель не найдена. Сначала обучите и сохраните модель.")
    predictor = TimeSeriesPredictor.load(MODEL_PATH)
    logging.info("Модель успешно загружена")
    return predictor

def read_logs():
    """
    Читает содержимое файла логов и возвращает текст.
    """
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            return f.read()
    return "Лог-файл отсутствует."
