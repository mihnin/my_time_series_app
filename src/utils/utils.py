# utils.py
import logging
import os
from logging.handlers import RotatingFileHandler
import sys

LOG_FILE = "logs/app.log"

def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    logger = logging.getLogger()
    logger.handlers = []

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s.%(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10000000,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("========== Приложение запущено ==========")

def read_logs() -> str:
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    try:
        with open(LOG_FILE, "r", encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Перекодировка при ошибке
        with open(LOG_FILE, 'rb') as old:
            data = old.read()
        with open(LOG_FILE, 'wb') as new:
            new.write(data.decode('cp1251', errors='replace').encode('utf-8'))
        with open(LOG_FILE, "r", encoding='utf-8') as f:
            return f.read()
