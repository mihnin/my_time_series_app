import os
from dotenv import load_dotenv
from pathlib import Path
from functools import cached_property

# Путь к файлу .env
ENV_PATH = Path(__file__).parent.parent / '.env'

def reload_env_vars():
    """Перезагружает переменные окружения из .env файла"""
    load_dotenv(dotenv_path=ENV_PATH, override=True)

# Первоначальная загрузка переменных окружения
reload_env_vars()

class Settings:
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 часа
    MODULE_READ_ONLY = False
    @property
    def DB_USER(self) -> str:
        return os.getenv('DB_USER', '')
    
    @property
    def DB_PASS(self) -> str:
        return os.getenv('DB_PASS', '')
    
    @property
    def DB_HOST(self) -> str:
        return os.getenv('DB_HOST', '')
    
    @property
    def DB_PORT(self) -> str:
        return os.getenv('DB_PORT', '')
    @property
    def DB_NAME(self) -> str:
        return os.getenv('DB_NAME', '')
    
    @property
    def SCHEMA(self) -> str:
        return os.getenv('DB_SCHEMA', '')
    
    @property
    def SECRET_KEY(self) -> str:
        return os.getenv('SECRET_KEY', '')
    
    @property
    def sqlalchemy_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def asyncpg_url(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    def refresh(self):
        """Обновляет значения переменных окружения, перезагружая их из файла .env"""
        reload_env_vars()


settings = Settings()
