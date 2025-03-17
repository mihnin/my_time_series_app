# src/utils/resource_monitor.py
import psutil
import threading
import time
import logging
import os
from typing import Dict, List, Optional, Tuple, Callable

# Пороговые значения для ресурсов системы (в процентах)
DEFAULT_CPU_THRESHOLD = 80.0     # Процент загрузки CPU
DEFAULT_MEMORY_THRESHOLD = 80.0  # Процент использования ОЗУ
DEFAULT_DISK_THRESHOLD = 90.0    # Процент использования диска

class ResourceMonitor:
    """Монитор системных ресурсов для обеспечения стабильности приложения"""
    _instance = None
    
    def __new__(cls):
        # Паттерн Singleton
        if cls._instance is None:
            cls._instance = super(ResourceMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        # Инициализация
        self.cpu_threshold = DEFAULT_CPU_THRESHOLD
        self.memory_threshold = DEFAULT_MEMORY_THRESHOLD
        self.disk_threshold = DEFAULT_DISK_THRESHOLD
        
        # Добавляем переменные для хранения последних значений
        self.last_cpu = 0.0
        self.last_memory = 0.0
        self.last_disk = 0.0
        
        self.monitor_thread = None
        self.running = False
        self.check_interval = 5  # секунды между проверками
        
        # История использования ресурсов (для отслеживания тенденций)
        self.max_history_size = 60  # Хранить 60 записей (5 минут при интервале 5 сек)
        self.cpu_history: List[float] = []
        self.memory_history: List[float] = []
        self.disk_history: List[float] = []
        
        # Колбеки для обработки критических ситуаций
        self.critical_callbacks: List[Callable] = []
        
        # Флаг состояния системы (True = нормальное)
        self.system_ok = True
        
        self._initialized = True
        logging.info("Монитор ресурсов инициализирован")
    
    def start_monitoring(self) -> None:
        """Запускает мониторинг ресурсов в отдельном потоке"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ResourceMonitorThread"
        )
        self.monitor_thread.start()
        logging.info("Запущен мониторинг системных ресурсов")
    
    def stop_monitoring(self) -> None:
        """Останавливает мониторинг ресурсов"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
            logging.info("Мониторинг системных ресурсов остановлен")
    
    def add_critical_callback(self, callback: Callable) -> None:
        """Добавляет функцию обратного вызова для критических ситуаций"""
        self.critical_callbacks.append(callback)
    
    def get_current_usage(self) -> Dict[str, float]:
        """Возвращает текущее использование ресурсов"""
        # Запоминаем текущие значения как предыдущие
        if hasattr(self, 'cpu_history') and self.cpu_history:
            self.last_cpu = self.cpu_history[-1]
        if hasattr(self, 'memory_history') and self.memory_history:
            self.last_memory = self.memory_history[-1]
        if hasattr(self, 'disk_history') and self.disk_history:
            self.last_disk = self.disk_history[-1]
        
        # Получаем новые значения
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        return {
            'cpu': cpu_percent,
            'memory': memory_percent,
            'disk': disk_percent
        }
    
    def get_usage_history(self) -> Dict[str, List[float]]:
        """Возвращает историю использования ресурсов"""
        return {
            'cpu': self.cpu_history.copy(),
            'memory': self.memory_history.copy(),
            'disk': self.disk_history.copy()
        }
    
    def set_thresholds(self, 
                      cpu_threshold: Optional[float] = None,
                      memory_threshold: Optional[float] = None,
                      disk_threshold: Optional[float] = None) -> None:
        """Устанавливает пороговые значения для мониторинга"""
        if cpu_threshold is not None:
            self.cpu_threshold = max(0.0, min(100.0, cpu_threshold))
        
        if memory_threshold is not None:
            self.memory_threshold = max(0.0, min(100.0, memory_threshold))
        
        if disk_threshold is not None:
            self.disk_threshold = max(0.0, min(100.0, disk_threshold))
        
        logging.info(f"Установлены новые пороги мониторинга: CPU={self.cpu_threshold}%, "
                    f"Память={self.memory_threshold}%, Диск={self.disk_threshold}%")
    
    def is_system_overloaded(self) -> Tuple[bool, Dict[str, bool]]:
        """Проверяет, перегружена ли система"""
        current = self.get_current_usage()
        
        cpu_overload = current['cpu'] > self.cpu_threshold
        memory_overload = current['memory'] > self.memory_threshold
        disk_overload = current['disk'] > self.disk_threshold
        
        is_overloaded = cpu_overload or memory_overload or disk_overload
        
        return is_overloaded, {
            'cpu': cpu_overload,
            'memory': memory_overload,
            'disk': disk_overload
        }
    
    def _monitoring_loop(self) -> None:
        """Основной цикл мониторинга ресурсов"""
        while self.running:
            try:
                # Получаем текущие значения
                current = self.get_current_usage()
                
                # Обновляем историю
                self.cpu_history.append(current['cpu'])
                self.memory_history.append(current['memory'])
                self.disk_history.append(current['disk'])
                
                # Ограничиваем размер истории
                if len(self.cpu_history) > self.max_history_size:
                    self.cpu_history.pop(0)
                if len(self.memory_history) > self.max_history_size:
                    self.memory_history.pop(0)
                if len(self.disk_history) > self.max_history_size:
                    self.disk_history.pop(0)
                
                # Проверяем на перегрузку
                is_overloaded, overload_info = self.is_system_overloaded()
                
                # Если состояние изменилось, логируем событие
                if is_overloaded != (not self.system_ok):
                    if is_overloaded:
                        overload_resources = [k for k, v in overload_info.items() if v]
                        logging.warning(f"ВНИМАНИЕ: Система перегружена! "
                                       f"Превышены пороги для: {', '.join(overload_resources)}")
                        self.system_ok = False
                        
                        # Вызываем колбеки для критических ситуаций
                        for callback in self.critical_callbacks:
                            try:
                                callback(overload_info)
                            except Exception as e:
                                logging.error(f"Ошибка в колбеке обработки критической ситуации: {e}")
                    else:
                        logging.info("Система вернулась в нормальное состояние")
                        self.system_ok = True
                
                # Логируем подробную информацию с периодичностью
                if int(time.time()) % 60 == 0:  # Каждую минуту
                    logging.info(f"Использование ресурсов: "
                               f"CPU={current['cpu']:.1f}%, "
                               f"Память={current['memory']:.1f}%, "
                               f"Диск={current['disk']:.1f}%")
                
                # Делаем паузу перед следующей проверкой
                time.sleep(self.check_interval)
                
            except Exception as e:
                logging.exception(f"Ошибка в цикле мониторинга ресурсов: {e}")
                time.sleep(10)  # При ошибке делаем большую паузу
    
    def can_accept_new_task(self) -> bool:
        """Проверяет, может ли система принять новую задачу"""
        # Если мониторинг не запущен, всегда разрешаем новые задачи
        if not self.running:
            return True
        
        # Проверяем текущую загрузку с более низкими порогами для новых задач
        current = self.get_current_usage()
        
        # Выводим текущее использование ресурсов в лог для отладки
        logging.info(f"Текущее использование ресурсов: CPU={current['cpu']:.1f}%, "
                    f"Память={current['memory']:.1f}%, Диск={current['disk']:.1f}%")
        
        # На мощных системах используем более высокие пороги 
        # (минимальный порог - 90% от максимального, чтобы всегда была возможность обучать модели)
        config_thresholds = self.get_config_thresholds()
        cpu_limit = max(80.0, config_thresholds.get('cpu_threshold', 90.0))
        memory_limit = max(85.0, config_thresholds.get('memory_threshold', 92.0))
        disk_limit = max(90.0, config_thresholds.get('disk_threshold', 95.0))
        
        # Для определения, может ли система принять новую задачу, проверяем только самые критичные ресурсы
        # Обучение модели больше всего зависит от памяти, поэтому в основном проверяем её
        safe_memory = current['memory'] < memory_limit
        
        # Проверяем CPU с более гибким порогом, т.к. кратковременные пики нагрузки допустимы
        safe_cpu = current['cpu'] < cpu_limit
        
        # Для диска проверяем только критический порог
        safe_disk = current['disk'] < disk_limit
        
        is_safe = safe_cpu and safe_memory and safe_disk
        
        if not is_safe:
            logging.info(f"Отказ в запуске новой задачи: "
                        f"CPU={current['cpu']:.1f}% (лимит {cpu_limit}%), "
                        f"Память={current['memory']:.1f}% (лимит {memory_limit}%), "
                        f"Диск={current['disk']:.1f}% (лимит {disk_limit}%)")
        
        return is_safe

    def get_config_thresholds(self):
        """Получает пороги из конфигурации"""
        try:
            from src.config.app_config import get_config
            config = get_config()
            return {
                'cpu_threshold': config.get('resource', {}).get('cpu_threshold', 95.0),
                'memory_threshold': config.get('resource', {}).get('memory_threshold', 98.0),
                'disk_threshold': config.get('resource', {}).get('disk_threshold', 95.0)
            }
        except Exception:
            # В случае ошибки возвращаем значения по умолчанию
            return {
                'cpu_threshold': 95.0,
                'memory_threshold': 98.0,
                'disk_threshold': 95.0
            }


# Глобальная функция для доступа к экземпляру монитора ресурсов
def get_resource_monitor() -> ResourceMonitor:
    """Возвращает экземпляр монитора ресурсов (синглтон)"""
    return ResourceMonitor()

# Функция для получения текущего статуса системы в формате для отображения
def get_system_status_info() -> Dict[str, any]:
    """Возвращает информацию о состоянии системы для отображения"""
    monitor = get_resource_monitor()
    current = monitor.get_current_usage()
    
    # Получаем информацию о доступных и занятых ресурсах
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Информация о процессоре
    cpu_count = psutil.cpu_count(logical=True)
    cpu_physical = psutil.cpu_count(logical=False)
    
    # Получаем состояние перегрузки
    is_overloaded, overload_info = monitor.is_system_overloaded()
    
    return {
        'cpu': {
            'percent': current['cpu'],
            'count': cpu_count,
            'physical_count': cpu_physical,
            'threshold': monitor.cpu_threshold,
            'overloaded': overload_info['cpu']
        },
        'memory': {
            'percent': current['memory'],
            'total_gb': memory.total / (1024 ** 3),
            'available_gb': memory.available / (1024 ** 3),
            'used_gb': (memory.total - memory.available) / (1024 ** 3),
            'threshold': monitor.memory_threshold,
            'overloaded': overload_info['memory']
        },
        'disk': {
            'percent': current['disk'],
            'total_gb': disk.total / (1024 ** 3),
            'free_gb': disk.free / (1024 ** 3),
            'used_gb': disk.used / (1024 ** 3),
            'threshold': monitor.disk_threshold,
            'overloaded': overload_info['disk']
        },
        'system_ok': monitor.system_ok,
        'is_overloaded': is_overloaded
    } 