# src/utils/logger.py
import logging
import os
import time
import threading
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import traceback

# Базовая директория для логов
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Создаем директорию для логов, если её нет
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# Настройка форматирования логов
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(module)s.%(funcName)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Настройка системы логирования
def setup_logger(log_level=logging.INFO):
    """Настраивает систему логирования с расширенной функциональностью"""
    
    # Создаем основной логгер
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Добавляем обработчик для вывода в файл
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(file_handler)
    
    # Добавляем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(console_handler)
    
    return logger

# Функция для чтения логов
def read_logs(max_lines: int = 1000) -> str:
    """Читает последние строки лог-файла"""
    if not os.path.exists(LOG_FILE):
        return "Лог-файл не найден."
    
    try:
        # Читаем последние max_lines строк
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-max_lines:]
        return ''.join(lines)
    except Exception as e:
        return f"Ошибка чтения лог-файла: {e}"

# Функция для очистки логов
def clear_logs() -> bool:
    """Очищает лог-файл"""
    try:
        if os.path.exists(LOG_FILE):
            # Предварительно делаем архивную копию
            archive_logs()
            
            # Очищаем файл
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write("")
            
            # Логируем событие
            logging.info("Лог-файл был очищен")
            return True
        return False
    except Exception as e:
        print(f"Ошибка при очистке лог-файла: {e}")
        return False

# Функция для архивирования логов
def archive_logs() -> str:
    """Создает архивную копию текущего лог-файла"""
    if not os.path.exists(LOG_FILE):
        return ""
    
    # Создаем каталог архивов, если его нет
    archive_dir = os.path.join(LOG_DIR, "archive")
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)
    
    # Формируем имя архивного файла с текущей датой и временем
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_file = os.path.join(archive_dir, f"app_log_{timestamp}.log")
    
    try:
        # Копируем содержимое в архив
        with open(LOG_FILE, 'r', encoding='utf-8') as src:
            content = src.read()
            
        with open(archive_file, 'w', encoding='utf-8') as dst:
            dst.write(content)
        
        return archive_file
    except Exception as e:
        print(f"Ошибка при архивировании лог-файла: {e}")
        return ""

# Класс для структурированного логирования
class StructuredLogger:
    """Класс для структурированного логирования с поддержкой JSON-формата"""
    
    def __init__(self, module_name: str):
        """Инициализирует логгер для указанного модуля"""
        self.module_name = module_name
        self.logger = logging.getLogger(module_name)
    
    def _format_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Форматирует дополнительные поля для структурированного логирования"""
        formatted = {"module": self.module_name}
        
        if extra:
            formatted.update(extra)
        
        return formatted
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Логирует информационное сообщение"""
        extra_formatted = self._format_extra(extra)
        
        # Форматируем структурированное сообщение
        if extra:
            struct_msg = f"{message} | {json.dumps(extra, default=str)}"
        else:
            struct_msg = message
        
        self.logger.info(struct_msg, extra=extra_formatted)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Логирует предупреждение"""
        extra_formatted = self._format_extra(extra)
        
        # Форматируем структурированное сообщение
        if extra:
            struct_msg = f"{message} | {json.dumps(extra, default=str)}"
        else:
            struct_msg = message
        
        self.logger.warning(struct_msg, extra=extra_formatted)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """Логирует ошибку"""
        extra_formatted = self._format_extra(extra)
        
        # Добавляем информацию об исключении, если оно произошло
        if exc_info:
            tb = traceback.format_exc()
            if extra is None:
                extra = {}
            extra["traceback"] = tb
        
        # Форматируем структурированное сообщение
        if extra:
            struct_msg = f"{message} | {json.dumps(extra, default=str)}"
        else:
            struct_msg = message
        
        self.logger.error(struct_msg, extra=extra_formatted, exc_info=exc_info)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """Логирует критическую ошибку"""
        extra_formatted = self._format_extra(extra)
        
        # Добавляем информацию об исключении, если оно произошло
        if exc_info:
            tb = traceback.format_exc()
            if extra is None:
                extra = {}
            extra["traceback"] = tb
        
        # Форматируем структурированное сообщение
        if extra:
            struct_msg = f"{message} | {json.dumps(extra, default=str)}"
        else:
            struct_msg = message
        
        self.logger.critical(struct_msg, extra=extra_formatted, exc_info=exc_info)
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Логирует отладочное сообщение"""
        extra_formatted = self._format_extra(extra)
        
        # Форматируем структурированное сообщение
        if extra:
            struct_msg = f"{message} | {json.dumps(extra, default=str)}"
        else:
            struct_msg = message
        
        self.logger.debug(struct_msg, extra=extra_formatted)
    
    def log_exception(self, exc: Exception, message: str = "Исключение", extra: Optional[Dict[str, Any]] = None) -> None:
        """Логирует исключение с подробной информацией"""
        if extra is None:
            extra = {}
        
        extra.update({
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc()
        })
        
        self.error(message, extra=extra, exc_info=True)
    
    def log_performance(self, operation: str, duration_ms: float, extra: Optional[Dict[str, Any]] = None) -> None:
        """Логирует информацию о производительности операции"""
        if extra is None:
            extra = {}
        
        extra.update({
            "operation": operation,
            "duration_ms": duration_ms
        })
        
        self.info(f"Операция '{operation}' выполнена за {duration_ms:.2f} мс", extra=extra)

# Контекстный менеджер для измерения времени выполнения
class TimedOperation:
    """Контекстный менеджер для измерения времени выполнения операции и логирования результата"""
    
    def __init__(self, operation_name: str, logger: Optional[Union[logging.Logger, StructuredLogger]] = None):
        """Инициализирует измеритель времени для указанной операции"""
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger()
        self.start_time = None
    
    def __enter__(self):
        """Начинает замер времени"""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Завершает замер времени и логирует результат"""
        if self.start_time is not None:
            end_time = time.time()
            duration_ms = (end_time - self.start_time) * 1000
            
            # Определяем тип логгера и логируем соответствующим образом
            if isinstance(self.logger, StructuredLogger):
                self.logger.log_performance(self.operation_name, duration_ms)
            else:
                self.logger.info(f"Операция '{self.operation_name}' выполнена за {duration_ms:.2f} мс")

# Функция-декоратор для измерения времени выполнения функций
def timed_function(logger=None, operation_name=None):
    """Декоратор, измеряющий время выполнения функции и логирующий результат"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Определяем имя операции
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Определяем логгер
            log = logger or logging.getLogger(func.__module__)
            
            start_time = time.time()
            
            try:
                # Выполняем функцию
                result = func(*args, **kwargs)
                
                # Вычисляем время выполнения
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Логируем результат
                if isinstance(log, StructuredLogger):
                    log.log_performance(op_name, duration_ms)
                else:
                    log.info(f"Функция '{op_name}' выполнена за {duration_ms:.2f} мс")
                
                return result
            
            except Exception as e:
                # При ошибке логируем исключение
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                if isinstance(log, StructuredLogger):
                    log.error(f"Ошибка в функции '{op_name}' (время: {duration_ms:.2f} мс)", 
                             extra={"exception": str(e)}, exc_info=True)
                else:
                    log.error(f"Ошибка в функции '{op_name}' (время: {duration_ms:.2f} мс): {e}", exc_info=True)
                
                # Пробрасываем исключение дальше
                raise
        
        return wrapper
    
    # Если декоратор вызван без аргументов, первым аргументом будет функция
    if callable(logger):
        func_to_decorate = logger
        logger = None
        return decorator(func_to_decorate)
    
    return decorator

# Получение логгера с улучшенным форматированием
def get_structured_logger(module_name: str) -> StructuredLogger:
    """Возвращает настроенный структурированный логгер для указанного модуля"""
    return StructuredLogger(module_name) 