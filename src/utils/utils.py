import logging
import os
from autogluon.timeseries import TimeSeriesPredictor

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

def read_logs() -> str:
    """Читает и возвращает содержимое лог-файла с игнорированием битых байт."""
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


