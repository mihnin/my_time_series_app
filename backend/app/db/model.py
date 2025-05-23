from pydantic import BaseModel, Field
from typing import Optional, List

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
    tables: List[str]
    detail: Optional[str] = None

# Модель для выбора таблицы (понадобится для обучения)
class TableSelectionRequest(BaseModel):
    table_name: str
    username: str # Теперь эти данные будут приходить из токена, но пока оставим для примера
    password: str # Аналогично
