import os
from dotenv import load_dotenv
from pathlib import Path

# Корректно загружаем .env из backend/app/.env
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')

class Settings:
    DB_USER: str = DB_USER
    DB_PASS: str = DB_PASS
    DB_HOST: str = DB_HOST
    DB_PORT: str = DB_PORT
    DB_NAME: str = DB_NAME
    SECRET_KEY: str = "KIgSBcy5vZ"
    ALGORITHM: str = "HS256"
    SCHEMA: str = "ts_data"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 часа
    @property
    def sqlalchemy_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def asyncpg_url(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
