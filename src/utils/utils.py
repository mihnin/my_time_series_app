# src/utils/utils.py
import logging
import os
from logging.handlers import RotatingFileHandler
import sys
import chardet

# Константы для работы с логами
LOGS_DIR = "logs"
LOG_FILE = os.path.join(LOGS_DIR, "app.log")

def setup_logger():
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
    logger = logging.getLogger()
    logger.handlers = []
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s.%(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10_000_000,
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
    """
    Читает содержимое лог-файла с автоматическим определением кодировки.
    При возникновении проблем с кодировкой выполняет конвертацию в UTF-8.
    
    Возвращает:
        str: Содержимое лог-файла
    """
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    
    # Сначала пытаемся открыть напрямую с UTF-8
    try:
        with open(LOG_FILE, "r", encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # При ошибке кодировки читаем в бинарном режиме и определяем кодировку
        try:
            with open(LOG_FILE, 'rb') as f:
                raw_data = f.read()
            
            # Определяем кодировку с помощью chardet
            detected = chardet.detect(raw_data)
            encoding = detected['encoding']
            confidence = detected['confidence']
            logging.info(f"Определена кодировка лог-файла: {encoding} (уверенность: {confidence:.2f})")
            
            if encoding and confidence > 0.7:
                # Используем определенную кодировку
                try:
                    return raw_data.decode(encoding)
                except Exception as e:
                    logging.warning(f"Не удалось декодировать лог-файл с кодировкой {encoding}: {e}")
            
            # Пробуем распространенные кодировки
            for enc in ['cp1251', 'iso-8859-1', 'cp866', 'koi8-r', 'latin1']:
                try:
                    text = raw_data.decode(enc, errors='replace')
                    logging.info(f"Успешное декодирование логов с кодировкой {enc}")
                    
                    # Конвертируем в UTF-8 и сохраняем для будущего использования
                    with open(LOG_FILE, 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    return text
                except Exception:
                    continue
            
            # Если все попытки не удались, возвращаем строку с заменой невалидных символов
            text = raw_data.decode('utf-8', errors='replace')
            logging.warning("Невозможно определить кодировку логов. Используется UTF-8 с заменой невалидных символов.")
            return text
        
        except Exception as e:
            logging.error(f"Критическая ошибка при чтении лог-файла: {e}")
            return f"Ошибка при чтении логов: {str(e)}"

