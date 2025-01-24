import logging
import os

LOG_FILE = "logs/app.log"

def setup_logger():
    if not os.path.exists("logs"):
        os.makedirs("logs")
    # Если Python 3.9+ – encoding="utf-8" сработает
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8"  # <-- Добавили, чтобы логи писались в UTF-8
    )
    logging.info("========== Приложение запущено ==========")

def read_logs() -> str:
    """
    Читаем лог-файл в UTF-8 (с заменой битых байт, если вдруг встретятся).
    """
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        return f.read()





