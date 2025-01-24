import logging
import os
from autogluon.timeseries import TimeSeriesPredictor

MODEL_PATH = "saved_models/ag_model"
LOG_FILE = "logs/app.log"

def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logging.info("========== Приложение запущено ==========")

def save_model(predictor: TimeSeriesPredictor, model_path: str = MODEL_PATH):
    """Сохраняет обученный предиктор AutoGluon."""
    if not os.path.exists("saved_models"):
        os.makedirs("saved_models")
    predictor.save(model_path)
    logging.info(f"Модель сохранена в {model_path}")

def load_model(model_path: str = MODEL_PATH) -> TimeSeriesPredictor:
    """Загружает обученный предиктор AutoGluon."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Нет модели по пути: {model_path}")
    predictor = TimeSeriesPredictor.load(model_path)
    logging.info(f"Модель загружена из {model_path}")
    return predictor

def read_logs() -> str:
    """Читает и возвращает содержимое лог-файла."""
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()

