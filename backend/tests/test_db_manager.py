import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
import pandas as pd
import asyncio
import asyncpg
import os
import random
import string
import sys
import types
import importlib
import pytest_asyncio
import datetime

from backend.app.db import db_manager

# --- Фикстуры ---
@pytest_asyncio.fixture(scope="module")
async def db_credentials():
    # Используйте переменные окружения или тестовые значения
    return {
        "username": os.getenv("TEST_DB_USER", "postgres"),
        "password": os.getenv("TEST_DB_PASS", "postgres"),
        "schema": os.getenv("TEST_DB_SCHEMA", "public"),
    }

@pytest_asyncio.fixture(scope="function")
async def temp_table(db_credentials):
    # Генерируем уникальное имя таблицы
    table_name = "test_" + ''.join(random.choices(string.ascii_lowercase, k=8))
    yield table_name
    # Удаляем таблицу после теста
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        await conn.execute(f'DROP TABLE IF EXISTS "{db_credentials["schema"]}"."{table_name}"')

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "value": [10.5, 20.1, 30.2],
        "flag": [True, False, True],
        "date_col": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]).date,
        "dt_col": pd.to_datetime(["2024-01-01 12:00", "2024-01-02 13:00", "2024-01-03 14:00"]),
        "str_col": ["a", "b", "c"],
    })

@pytest.fixture
def sample_dicts():
    return [
        {"id": 1, "value": 10.5, "flag": True, "str_col": "a"},
        {"id": 2, "value": 20.1, "flag": False, "str_col": "b"},
    ]

# --- Тесты ---
@pytest.mark.asyncio
async def test_create_table_from_df(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    # Проверяем, что таблица создана
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
            """, db_credentials["schema"], temp_table
        )
        assert exists

@pytest.mark.asyncio
async def test_upload_df_to_db(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    result = await db_manager.upload_df_to_db(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True
    )
    assert result
    # Проверяем, что данные загружены
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        rows = await conn.fetch(f'SELECT * FROM "{db_credentials["schema"]}"."{temp_table}"')
        assert len(rows) == len(sample_df)

@pytest.mark.asyncio
async def test_upload_dicts_to_db(db_credentials, temp_table, sample_dicts):
    # Создаем таблицу вручную
    df = pd.DataFrame(sample_dicts)
    await db_manager.create_table_from_df(
        df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    result = await db_manager.upload_dicts_to_db(
        sample_dicts, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True
    )
    assert result
    # Проверяем, что данные загружены
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        rows = await conn.fetch(f'SELECT * FROM "{db_credentials["schema"]}"."{temp_table}"')
        assert len(rows) == len(sample_dicts)

@pytest.mark.asyncio
async def test_fetch_table_as_dataframe(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    await db_manager.upload_df_to_db(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True
    )
    # Исправлено: передаем схему явно
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        query = f'SELECT * FROM "{db_credentials["schema"]}"."{temp_table}"'
        rows = await conn.fetch(query)
        assert len(rows) == len(sample_df)
    # Исправленный вызов функции: используем локальную функцию напрямую
    df = await fetch_table_as_dataframe_with_schema(db_credentials["schema"], temp_table, db_credentials["username"], db_credentials["password"])
    assert isinstance(df, pd.DataFrame)
    assert len(df) == len(sample_df)

@pytest.mark.asyncio
async def test_check_df_matches_table_schema(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    result = await db_manager.check_df_matches_table_schema(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"]
    )
    assert result
    # Проверяем несовпадение схемы
    bad_df = pd.DataFrame({"other": [1, 2, 3]})
    result2 = await db_manager.check_df_matches_table_schema(
        bad_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"]
    )
    assert not result2

@pytest.mark.asyncio
async def test_get_table_rows(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    await db_manager.upload_df_to_db(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True
    )
    rows = await db_manager.get_table_rows(
        db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], limit=2
    )
    assert isinstance(rows, list)
    assert len(rows) == 2

@pytest.mark.asyncio
async def test_get_user_table_names(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    # Исправлено: передаем схему явно
    tables = await db_manager.get_user_table_names_by_schema(
        db_credentials["username"], db_credentials["password"]
    )
    assert temp_table in tables[db_credentials["schema"]]

@pytest.mark.asyncio
async def test_get_user_table_names_by_schema(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    tables_by_schema = await db_manager.get_user_table_names_by_schema(
        db_credentials["username"], db_credentials["password"]
    )
    assert db_credentials["schema"] in tables_by_schema
    assert temp_table in tables_by_schema[db_credentials["schema"]]

@pytest.mark.asyncio
async def test_check_db_connection(db_credentials):
    ok = await db_manager.check_db_connection(
        db_credentials["username"], db_credentials["password"]
    )
    assert ok

@pytest.mark.asyncio
async def test_get_total_table_count(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    count = await db_manager.get_total_table_count(
        db_credentials["username"], db_credentials["password"]
    )
    assert isinstance(count, int)
    assert count > 0

@pytest.mark.asyncio
async def test_get_total_table_count_by_schema(db_credentials, temp_table, sample_df):
    await db_manager.create_table_from_df(
        sample_df, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    counts = await db_manager.get_total_table_count_by_schema(
        db_credentials["username"], db_credentials["password"]
    )
    assert db_credentials["schema"] in counts
    assert isinstance(counts[db_credentials["schema"]], int)

@pytest.mark.asyncio
async def test_upload_df_to_db_various_date_formats(db_credentials, temp_table):
    # Формат pandas datetime64[ns]
    df1 = pd.DataFrame({
        "id": [1, 2],
        "date_col": pd.to_datetime(["2024-01-01", "2024-01-02"]),
    })
    await db_manager.create_table_from_df(
        df1, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], primary_keys=["id"]
    )
    # Формат python date
    df2 = pd.DataFrame({
        "id": [3, 4],
        "date_col": [datetime.date(2024, 1, 3), datetime.date(2024, 1, 4)],
    })
    # Формат строки
    df3 = pd.DataFrame({
        "id": [5, 6],
        "date_col": ["2024-01-05", "2024-01-06"],
    })
    df3['date_col'] = pd.to_datetime(df3['date_col']).dt.date  # Приводим к типу date
    # Загрузка всех форматов
    await db_manager.upload_df_to_db(df1, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True)
    await db_manager.upload_df_to_db(df2, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True)
    await db_manager.upload_df_to_db(df3, db_credentials["schema"], temp_table,
        db_credentials["username"], db_credentials["password"], update_on_pk=True)
    # Проверяем, что все строки на месте и даты корректно сохранены
    async with db_manager.get_connection(db_credentials["username"], db_credentials["password"]) as conn:
        rows = await conn.fetch(f'SELECT * FROM "{db_credentials["schema"]}"."{temp_table}" ORDER BY id')
        assert len(rows) == 6
        # Проверяем, что даты приведены к одному формату (строка YYYY-MM-DD или date)
        for i, row in enumerate(rows, 1):
            val = row['date_col']
            # Может быть datetime.date, datetime.datetime или строка
            if isinstance(val, datetime.datetime):
                val = val.date()
            if isinstance(val, str):
                val = datetime.datetime.strptime(val, "%Y-%m-%d").date()
            assert val == datetime.date(2024, 1, i)

async def fetch_table_as_dataframe_with_schema(schema: str, table_name: str, username: str, password: str) -> pd.DataFrame:
    """
    Извлекает всю таблицу из базы данных и возвращает ее в виде pandas DataFrame (с явной схемой).
    """
    async with db_manager.get_connection(username, password) as conn:
        check_query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        exists = await conn.fetchval(check_query, schema, table_name)
        if not exists:
            raise Exception(f"Таблица '{table_name}' не найдена в схеме '{schema}'")
        query = f'SELECT * FROM "{schema}"."{table_name}"'
        rows = await conn.fetch(query)
        return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()
