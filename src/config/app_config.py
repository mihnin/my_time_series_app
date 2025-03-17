# src/config/app_config.py
import os
import yaml
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# Путь к файлу конфигурации
CONFIG_PATH = "config/config.yaml"

@dataclass
class QueueConfig:
    """Конфигурация системы очередей"""
    max_workers: int = 3  # Максимальное количество одновременно выполняемых задач
    task_timeout: int = 3600  # Таймаут задачи в секундах (1 час)
    clean_interval: int = 3600  # Интервал очистки завершенных задач в секундах (1 час)
    max_task_age: int = 86400  # Максимальный возраст завершенных задач в секундах (24 часа)

@dataclass
class SessionConfig:
    """Конфигурация управления сессиями"""
    session_ttl: int = 24  # Время жизни сессии в часах
    session_dir: str = "data/sessions"  # Каталог для хранения сессий
    clean_interval: int = 3600  # Интервал очистки старых сессий в секундах (1 час)

@dataclass
class ResourceConfig:
    """Конфигурация мониторинга ресурсов"""
    cpu_threshold: float = 90.0  # Порог загрузки CPU (%)
    memory_threshold: float = 95.0  # Порог использования памяти (%)
    disk_threshold: float = 95.0  # Порог использования диска (%)
    check_interval: int = 5  # Интервал проверки ресурсов в секундах

@dataclass
class LoggingConfig:
    """Конфигурация системы логирования"""
    log_dir: str = "logs"  # Каталог для хранения логов
    log_level: str = "INFO"  # Уровень логирования
    log_format: str = "%(asctime)s [%(levelname)s] %(module)s.%(funcName)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    max_log_size: int = 10485760  # Максимальный размер лог-файла (10MB)
    backup_count: int = 5  # Количество резервных копий лог-файла

@dataclass
class UIConfig:
    """Конфигурация пользовательского интерфейса"""
    theme: str = "light"  # Тема интерфейса (light/dark)
    primary_color: str = "#1E88E5"  # Основной цвет
    secondary_color: str = "#4CAF50"  # Дополнительный цвет
    error_color: str = "#E53935"  # Цвет ошибок
    warning_color: str = "#FFA726"  # Цвет предупреждений
    info_color: str = "#29B6F6"  # Цвет информационных сообщений
    max_graphs_per_page: int = 5  # Максимальное количество графиков на странице

@dataclass
class AppConfig:
    """Основная конфигурация приложения"""
    app_name: str = "Бизнес-приложение для прогнозирования временных рядов"
    app_version: str = "2.1.0"
    debug_mode: bool = False
    model_dir: str = "AutogluonModels/TimeSeriesModel"  # Каталог для хранения моделей
    data_dir: str = "data"  # Каталог для хранения данных
    
    # Вложенные конфигурации
    queue: QueueConfig = field(default_factory=QueueConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    resource: ResourceConfig = field(default_factory=ResourceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    
    # Словари из конфигурационного файла
    auto_detection: Dict[str, Any] = field(default_factory=dict)
    metrics_dict: Dict[str, str] = field(default_factory=dict)
    ag_models: Dict[str, str] = field(default_factory=dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение атрибута по его имени
        
        Parameters:
        -----------
        key : str
            Имя атрибута
        default : Any, optional
            Значение по умолчанию, если атрибут не найден
        
        Returns:
        --------
        Any
            Значение атрибута или значение по умолчанию
        """
        # Проверяем наличие атрибута напрямую
        if hasattr(self, key):
            return getattr(self, key)
        
        # Проверяем вложенные словари конфигурации
        if key in self.auto_detection:
            return self.auto_detection[key]
        if key in self.metrics_dict:
            return self.metrics_dict[key]
        if key in self.ag_models:
            return self.ag_models[key]
        
        # Проверяем вложенные конфигурации
        for config_obj_name in ['queue', 'session', 'resource', 'logging', 'ui']:
            config_obj = getattr(self, config_obj_name)
            if hasattr(config_obj, key):
                return getattr(config_obj, key)
        
        # Возвращаем значение по умолчанию, если атрибут не найден
        return default

def load_config_from_yaml(config_path: str) -> Dict[str, Any]:
    """
    Загружает конфигурацию из YAML файла
    
    Parameters:
    -----------
    config_path : str
        Путь к файлу конфигурации
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с конфигурацией
    """
    try:
        if not os.path.exists(config_path):
            logging.warning(f"Файл конфигурации {config_path} не найден. Будут использованы значения по умолчанию.")
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            logging.warning(f"Файл конфигурации {config_path} пуст или имеет неправильный формат. Будут использованы значения по умолчанию.")
            return {}
        
        return config_data
    except Exception as e:
        logging.error(f"Ошибка при загрузке конфигурации: {e}")
        return {}

def create_config() -> AppConfig:
    """
    Создает экземпляр AppConfig с данными из файла конфигурации
    
    Returns:
    --------
    AppConfig
        Конфигурация приложения
    """
    config_data = load_config_from_yaml(CONFIG_PATH)
    
    # Создаем базовую конфигурацию
    app_config = AppConfig()
    
    # Устанавливаем основные параметры
    if 'app_name' in config_data:
        app_config.app_name = config_data['app_name']
    if 'app_version' in config_data:
        app_config.app_version = config_data['app_version']
    if 'debug_mode' in config_data:
        app_config.debug_mode = config_data['debug_mode']
    if 'model_dir' in config_data:
        app_config.model_dir = config_data['model_dir']
    if 'data_dir' in config_data:
        app_config.data_dir = config_data['data_dir']
    
    # Устанавливаем настройки очереди
    if 'queue' in config_data:
        queue_config = config_data['queue']
        app_config.queue = QueueConfig(
            max_workers=queue_config.get('max_workers', app_config.queue.max_workers),
            task_timeout=queue_config.get('task_timeout', app_config.queue.task_timeout),
            clean_interval=queue_config.get('clean_interval', app_config.queue.clean_interval),
            max_task_age=queue_config.get('max_task_age', app_config.queue.max_task_age)
        )
    
    # Устанавливаем настройки сессий
    if 'session' in config_data:
        session_config = config_data['session']
        app_config.session = SessionConfig(
            session_ttl=session_config.get('session_ttl', app_config.session.session_ttl),
            session_dir=session_config.get('session_dir', app_config.session.session_dir),
            clean_interval=session_config.get('clean_interval', app_config.session.clean_interval)
        )
    
    # Устанавливаем настройки ресурсов
    if 'resource' in config_data:
        resource_config = config_data['resource']
        app_config.resource = ResourceConfig(
            cpu_threshold=resource_config.get('cpu_threshold', app_config.resource.cpu_threshold),
            memory_threshold=resource_config.get('memory_threshold', app_config.resource.memory_threshold),
            disk_threshold=resource_config.get('disk_threshold', app_config.resource.disk_threshold),
            check_interval=resource_config.get('check_interval', app_config.resource.check_interval)
        )
    
    # Устанавливаем настройки логирования
    if 'logging' in config_data:
        logging_config = config_data['logging']
        app_config.logging = LoggingConfig(
            log_dir=logging_config.get('log_dir', app_config.logging.log_dir),
            log_level=logging_config.get('log_level', app_config.logging.log_level),
            log_format=logging_config.get('log_format', app_config.logging.log_format),
            date_format=logging_config.get('date_format', app_config.logging.date_format),
            max_log_size=logging_config.get('max_log_size', app_config.logging.max_log_size),
            backup_count=logging_config.get('backup_count', app_config.logging.backup_count)
        )
    
    # Устанавливаем настройки UI
    if 'ui' in config_data:
        ui_config = config_data['ui']
        app_config.ui = UIConfig(
            theme=ui_config.get('theme', app_config.ui.theme),
            primary_color=ui_config.get('primary_color', app_config.ui.primary_color),
            secondary_color=ui_config.get('secondary_color', app_config.ui.secondary_color),
            error_color=ui_config.get('error_color', app_config.ui.error_color),
            warning_color=ui_config.get('warning_color', app_config.ui.warning_color),
            info_color=ui_config.get('info_color', app_config.ui.info_color),
            max_graphs_per_page=ui_config.get('max_graphs_per_page', app_config.ui.max_graphs_per_page)
        )
    
    # Копируем настройки автоопределения полей
    if 'auto_detection' in config_data:
        app_config.auto_detection = config_data['auto_detection']
        # Явно отключаем определение частоты, даже если в конфигурации указано иначе
        if 'frequency_enabled' in app_config.auto_detection:
            app_config.auto_detection['frequency_enabled'] = False
    else:
        # Если секции auto_detection нет, создаем ее с отключенным определением частоты
        app_config.auto_detection = {
            'fields_enabled': True,
            'frequency_enabled': False
        }
    
    # Копируем словари метрик и моделей
    if 'metrics_dict' in config_data:
        app_config.metrics_dict = config_data['metrics_dict']
    
    if 'ag_models' in config_data:
        app_config.ag_models = config_data['ag_models']
    
    return app_config

# Инициализируем глобальный экземпляр конфигурации
app_config = create_config()

def get_config(field_name=None) -> Any:
    """
    Возвращает текущую конфигурацию приложения или конкретное поле конфигурации
    
    Parameters:
    -----------
    field_name : str, optional
        Имя поля конфигурации, которое нужно вернуть
        
    Returns:
    --------
    Any
        Конфигурация приложения или значение конкретного поля
    """
    global app_config
    
    if field_name is None:
        return app_config
        
    # Обрабатываем случай, когда поле - это специальная константа
    if field_name == "MODEL_DIR":
        return app_config.model_dir
    elif field_name == "MODEL_INFO_FILE":
        return "model_info.json"
    elif field_name == "DATA_DIR":
        return app_config.data_dir
    
    # Пытаемся получить поле из основной конфигурации
    if hasattr(app_config, field_name):
        return getattr(app_config, field_name)
    
    # Если прямого поля нет, ищем в словарях конфигурации
    if field_name in app_config.auto_detection:
        return app_config.auto_detection[field_name]
    if field_name in app_config.metrics_dict:
        return app_config.metrics_dict[field_name]
    if field_name in app_config.ag_models:
        return app_config.ag_models[field_name]
    
    # Если поле не найдено, возвращаем None или можно вызвать исключение
    logging.warning(f"Запрошено несуществующее поле конфигурации: {field_name}")
    return None

def reload_config() -> AppConfig:
    """
    Перезагружает конфигурацию из файла
    
    Returns:
    --------
    AppConfig
        Обновленная конфигурация приложения
    """
    global app_config
    app_config = create_config()
    return app_config

# Создаем нужные директории при импорте модуля
os.makedirs(app_config.logging.log_dir, exist_ok=True)
os.makedirs(app_config.session.session_dir, exist_ok=True)
os.makedirs(app_config.data_dir, exist_ok=True)
os.makedirs(os.path.dirname(app_config.model_dir), exist_ok=True) 