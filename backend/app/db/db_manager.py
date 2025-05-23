import io
import asyncpg
import pandas as pd
from contextlib import asynccontextmanager
from .settings import settings
from typing import List, Dict, Any


# --- Контекстный менеджер подключения ---
@asynccontextmanager
async def get_connection(username: str, password: str):
    """
    Асинхронный контекстный менеджер для получения подключения к базе данных.
    Гарантирует закрытие соединения после использования.
    """
    conn = await asyncpg.connect(
        user=username,
        password=password,
        database=settings.DB_NAME,
        host=settings.DB_HOST,
        port=int(settings.DB_PORT)
    )
    try:
        yield conn
    finally:
        await conn.close()


# --- Соответствие типов pandas -> PostgreSQL ---
DTYPE_MAP = {
    'int64': 'BIGINT',
    'float64': 'DOUBLE PRECISION',
    'bool': 'BOOLEAN',
    'datetime64[ns]': 'TIMESTAMP',
    'object': 'TEXT',
    'string': 'TEXT',
}


# --- Получение таблицы как DataFrame ---
async def fetch_table_as_dataframe(table_name: str, username: str, password: str) -> pd.DataFrame:
    """
    Извлекает всю таблицу из базы данных и возвращает ее в виде pandas DataFrame.
    """
    async with get_connection(username, password) as conn:
        check_query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        exists = await conn.fetchval(check_query, settings.SCHEMA, table_name)
        if not exists:
            raise Exception(f"Таблица {table_name} не найдена")

        query = f'SELECT * FROM "{settings.SCHEMA}"."{table_name}"'
        rows = await conn.fetch(query)
        return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


# --- Создание таблицы из DataFrame ---
async def create_table_from_df(df: pd.DataFrame, table_name: str, username: str, password: str) -> None:
    """
    Создает новую таблицу в базе данных на основе структуры DataFrame.
    Если таблица уже существует, будет вызвана ошибка.
    Эта функция не заполняет таблицу значениями.
    """
    async with get_connection(username, password) as conn:
        check_table_exists_query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        table_exists = await conn.fetchval(check_table_exists_query, settings.SCHEMA, table_name)
        if table_exists:
            raise Exception(f"Таблица '{table_name}' уже существует.")

        columns = []
        for col in df.columns:
            pd_type = str(df[col].dtype)
            sql_type = DTYPE_MAP.get(pd_type, 'TEXT')
            columns.append(f'"{col}" {sql_type}')
        columns_sql = ', '.join(columns)
        create_query = f'CREATE TABLE "{settings.SCHEMA}"."{table_name}" ({columns_sql})'
        await conn.execute(create_query)


# --- Загрузка DataFrame в существующую таблицу ---
async def upload_df_to_db(df: pd.DataFrame, table_name: str, username: str, password: str) -> bool:
    """
    Загружает pandas DataFrame в существующую таблицу в базе данных.
    Таблица должна быть создана заранее.
    """
    async with get_connection(username, password) as conn:
        if not df.empty:
            records = df.where(pd.notnull(df), None).to_dict(orient='records')
            columns_str = ', '.join([f'"{col}"' for col in df.columns])
            values_template = ', '.join([f'${i+1}' for i in range(len(df.columns))])
            insert_query = f'INSERT INTO "{settings.SCHEMA}"."{table_name}" ({columns_str}) VALUES ({values_template})'
            await conn.executemany(insert_query, [list(record.values()) for record in records])
    return True


# --- Предпросмотр таблицы с лимитом строк ---
async def get_table_rows(
    table_name: str, username: str, password: str, limit: int | None = None
) -> list[dict]:
    """
    Выбирает ограниченное количество строк из указанной таблицы для предпросмотра.
    """
    async with get_connection(username, password) as conn:
        # Получаем список таблиц в схеме
        valid_tables_query = """
            SELECT tablename 
            FROM pg_catalog.pg_tables 
            WHERE schemaname = $1
        """
        valid_tables = await conn.fetch(valid_tables_query, settings.SCHEMA)
        valid_table_names = {row["tablename"] for row in valid_tables}

        if table_name not in valid_table_names:
            raise ValueError(f"Invalid table name: '{table_name}'")

        # Проверяем и формируем SQL-запрос
        if limit is not None:
            if not (1 <= limit <= 10**10):
                raise ValueError("Limit out of range")
            query = f'SELECT * FROM "{settings.SCHEMA}"."{table_name}" LIMIT {limit}'
        else:
            query = f'SELECT * FROM "{settings.SCHEMA}"."{table_name}"'

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]


# --- Получение доступных пользователю таблиц ---
async def get_user_table_names(username: str, password: str) -> List[str]:
    """
    Возвращает список имен таблиц, к которым текущий пользователь имеет привилегию SELECT.
    """
    async with get_connection(username, password) as conn:
        query = f"""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = '{settings.SCHEMA}'
            AND has_table_privilege(current_user, concat(schemaname, '.', tablename), 'SELECT')
        """
        tables = await conn.fetch(query)
        return [record['tablename'] for record in tables]


# --- Проверка подключения к БД ---
async def check_db_connection(username: str, password: str) -> bool:
    """
    Проверяет возможность подключения к базе данных с предоставленными учетными данными.
    """
    try:
        async with get_connection(username, password) as conn:
            # Если соединение успешно установлено и закрыто, значит, учетные данные верны.
            return True
    except Exception:
        return False
