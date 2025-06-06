from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Запрос на проверку подключения/логин
class DBConnectionRequest(BaseModel):
    username: str
    password: str

# Ответ на проверку подключения
class DBConnectionResponse(BaseModel):
    success: bool
    detail: str
    access_token: Optional[str] = None  # Добавляем токен
    token_type: Optional[str] = "bearer" # Тип токена

# Модель для данных JWT (payload)
class TokenData(BaseModel):
    username: Optional[str] = None # Логин пользователя БД, на основе которого выдан токен

# Модель для ответа со списком таблиц
class TablesResponse(BaseModel):
    success: bool
    tables: Dict[str, List[str]]  # {schema: [table1, table2, ...]}
    count_available: int
    count_total: int
    detail: Optional[str] = None

# Модель для выбора таблицы (понадобится для обучения)
class TableSelectionRequest(BaseModel):
    table_name: str
    username: str # Теперь эти данные будут приходить из токена, но пока оставим для примера
    password: str # Аналогично

# --- Новые модели для API ---
class SecretKeyRequest(BaseModel):
    secret_key: str

class SecretKeyResponse(BaseModel):
    success: bool
    message: str
    
class EnvUpdateRequest(BaseModel):
    secret_key: str
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_SCHEMA: str

class EnvUpdateResponse(BaseModel):
    success: bool
    message: str

# --- Эндпоинты ---

class EnvVarsResponse(SecretKeyResponse):
    db_vars: dict = {}

class TablePreviewRequest(BaseModel):
    schema: str
    table: str

class DownloadTableRequest(BaseModel):
    schema: str
    table: str

class SavePredictionRequest(BaseModel):
    schema: str
    session_id: str
    table_name: str
    create_new: Optional[bool] = False

class CreateTableFromFileRequest(BaseModel):
    schema: str
    table_name: str
    primary_keys: Optional[list] = None
    create_table_only: Optional[bool] = False

class CheckDFMatchesTableSchemaRequest(BaseModel):
    schema: str
    table_name: str