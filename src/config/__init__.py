# src/config/__init__.py
# Пустой файл, чтобы директория считалась пакетом Python 

# Импортируем typing.Any для обновленной функции get_config
from typing import Any

# Импортируем функции, которые должны быть доступны при импорте из пакета
from .app_config import get_config, reload_config, app_config, AppConfig 