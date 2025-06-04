import io
import asyncpg
import pandas as pd
from contextlib import asynccontextmanager
from typing import List, Dict, Any
from functools import wraps
from .settings import settings


def auto_convert_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Автоматически приводит все object-столбцы к datetime, если все не-null значения успешно преобразуются.
    Всегда сохраняет как datetime (TIMESTAMP), не приводит к типу date.
    Возвращает новый DataFrame (копия).
    """
    df = df.copy()
    for col in df.select_dtypes(include=['object']).columns:
        orig_notnull = df[col].notnull()
        converted = pd.to_datetime(df[col], errors='coerce')
        if (converted.notna() | ~orig_notnull).all():
            df[col] = converted
    # Не преобразуем к date, всегда оставляем datetime64[ns]
    return df

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
    'int64': 'DOUBLE PRECISION',  # Всегда float
    'float64': 'DOUBLE PRECISION',
    'bool': 'BOOLEAN',
    'datetime64[ns]': 'TIMESTAMP',
    'object': 'TEXT',
    'string': 'TEXT',
}

# --- Обратное соответствие типов PostgreSQL -> pandas ---
PG_TO_PD_TYPE_MAP = {
    'bigint': 'int64',
    'integer': 'int64',
    'smallint': 'int64',
    'double precision': 'float64',
    'real': 'float64',
    'numeric': 'float64',
    'boolean': 'bool',
    'timestamp': 'datetime64[ns]',
    'timestamp with time zone': 'datetime64[ns]',
    'timestamp without time zone': 'datetime64[ns]',
    'text': 'object',
    'character varying': 'object',
    'varchar': 'object',
    'char': 'object',
}

# --- Декоратор для режима только для чтения ---
def read_only_guard(func):
    """
    Декоратор, который предотвращает выполнение функции, если settings.module_read_only = True.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if settings.MODULE_READ_ONLY:
            raise PermissionError(f"Функция '{func.__name__}' недоступна в режиме только для чтения.")
        return await func(*args, **kwargs)
    return wrapper


# --- Получение таблицы как DataFrame ---
async def fetch_table_as_dataframe(table_name: str, username: str, password: str) -> pd.DataFrame:
    """
    Извлекает всю таблицу из базы данных и возвращает ее в виде pandas DataFrame.
    """
    async with get_connection(username, password) as conn:
        # Проверяем существование таблицы
        check_query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        exists = await conn.fetchval(check_query, settings.SCHEMA, table_name)
        if not exists:
            raise Exception(f"Таблица '{table_name}' не найдена в схеме '{settings.SCHEMA}'")

        # Формируем запрос для выбора всех данных из таблицы
        query = f'SELECT * FROM "{settings.SCHEMA}"."{table_name}"'
        rows = await conn.fetch(query)
        return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()


# --- Создание таблицы из DataFrame ---
@read_only_guard
async def create_table_from_df(df: pd.DataFrame, schema: str, table_name: str, username: str, password: str, primary_keys: list = None) -> None:
    """
    Создает новую таблицу в базе данных на основе структуры DataFrame.
    Все числовые столбцы будут иметь тип DOUBLE PRECISION (float).
    Если таблица уже существует, будет вызвана ошибка.
    Эта функция не заполняет таблицу значениями.
    primary_keys: список колонок, которые будут использоваться как первичный ключ (или пустой список/None)
    """
    if primary_keys:
        if not isinstance(primary_keys, list):
            raise TypeError("primary_keys должен быть списком.")
        for pk in primary_keys:
            if pk not in df.columns:
                raise ValueError(f"Столбец первичного ключа '{pk}' не найден в DataFrame.")

    async with get_connection(username, password) as conn:
        # Проверяем существование таблицы
        check_table_exists_query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
        """
        table_exists = await conn.fetchval(check_table_exists_query, schema, table_name)
        if table_exists:
            raise Exception(f"Таблица '{table_name}' уже существует.")

        columns = []
        for col in df.columns:
            pd_type = str(df[col].dtype)
            # Все int и float -> DOUBLE PRECISION
            if pd_type.startswith('int') or pd_type.startswith('float'):
                sql_type = 'DOUBLE PRECISION'
            elif pd_type == 'datetime64[ns]':
                sql_type = 'TIMESTAMP'
            elif pd_type == 'bool':
                sql_type = 'BOOLEAN'
            elif pd_type == 'object':
                # Не определяем DATE, всегда TIMESTAMP для дат
                import datetime
                non_null = df[col].dropna()
                if not non_null.empty and all(isinstance(x, datetime.datetime) for x in non_null):
                    sql_type = 'TIMESTAMP'
                else:
                    sql_type = DTYPE_MAP.get(pd_type, 'TEXT')
            elif pd_type == 'string':
                sql_type = 'TEXT'
            elif pd_type == 'date':
                # Не используем DATE, всегда TIMESTAMP
                sql_type = 'TIMESTAMP'
            else:
                sql_type = DTYPE_MAP.get(pd_type, 'TEXT')
            columns.append(f'"{col}" {sql_type}')

        columns_sql = ', '.join(columns)
        pk_sql = ''
        if primary_keys and len(primary_keys) > 0:
            pk_cols = ', '.join([f'"{col}"' for col in primary_keys])
            if pk_cols:
                pk_sql = f', PRIMARY KEY ({pk_cols})'
        
        # Формируем запрос для создания таблицы
        create_query = f'CREATE TABLE "{schema}"."{table_name}" ({columns_sql}{pk_sql})'
        await conn.execute(create_query)


async def _get_pk_columns(conn: asyncpg.Connection, schema: str, table_name: str) -> List[str]:
    """
    Вспомогательная функция для получения списка столбцов первичного ключа
    для указанной таблицы из information_schema.
    """
    query = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = $1
          AND tc.table_name = $2;
    """
    try:
        pk_records = await conn.fetch(query, schema, table_name)
        return [record['column_name'] for record in pk_records]
    except Exception as e:
        print(f"Ошибка при получении первичного ключа для {schema}.{table_name}: {e}")
        return []
    
@read_only_guard
async def upload_df_to_db(
    df: pd.DataFrame,
    schema: str,
    table_name: str,
    username: str,
    password: str,
    update_on_pk: bool = True,
) -> bool:
    """
    Загружает pandas DataFrame в существующую таблицу в базе данных.
    Таблица должна быть создана заранее.

    Если update_on_pk=True, функция попытается автоматически определить
    первичный ключ таблицы и выполнить "upsert" (INSERT ON CONFLICT UPDATE).
    """
    def convert_dates_for_db(val, dtype=None):
        import datetime
        if dtype == 'datetime64[ns]':
            # asyncpg ожидает datetime.datetime для TIMESTAMP
            if isinstance(val, datetime.datetime):
                return val
            if isinstance(val, datetime.date):
                return datetime.datetime(val.year, val.month, val.day)
            if isinstance(val, str):
                try:
                    return datetime.datetime.strptime(val, '%Y-%m-%d')
                except Exception:
                    try:
                        return datetime.datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        return None
            return None
        return val

    async with get_connection(username, password) as conn:
        if not df.empty:
            pk_columns = []
            if update_on_pk:
                # Получаем первичный ключ из БД
                pk_columns = await _get_pk_columns(conn, schema, table_name)

                if not pk_columns:
                    # Если нет PK, просто делаем обычный insert без upsert
                    update_on_pk = False
                elif not all(col in df.columns for col in pk_columns):
                    missing_cols = [col for col in pk_columns if col not in df.columns]
                    raise ValueError(
                        f"DataFrame не содержит столбцы первичного ключа "
                        f"{missing_cols}, необходимые для update_on_pk."
                    )

            # Преобразуем NaN в None и корректно обрабатываем даты/строки
            records = df.where(pd.notnull(df), None).to_dict(orient='records')
            dtypes = {col: str(df[col].dtype) for col in df.columns}
            records = [
                {k: convert_dates_for_db(v, dtypes.get(k)) for k, v in rec.items()}
                for rec in records
            ]

            columns_str = ', '.join([f'"{col}"' for col in df.columns])
            values_template = ', '.join([f'${i+1}' for i in range(len(df.columns))])

            insert_query = f'INSERT INTO "{schema}"."{table_name}" ({columns_str}) VALUES ({values_template})'

            # Добавляем ON CONFLICT, если нужно
            if update_on_pk and pk_columns: # pk_columns здесь точно не пустой
                pk_columns_str = ', '.join([f'"{col}"' for col in pk_columns])
                update_cols = [col for col in df.columns if col not in pk_columns]

                if update_cols:
                    update_set_str = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in update_cols])
                    insert_query += f' ON CONFLICT ({pk_columns_str}) DO UPDATE SET {update_set_str}'
                else:
                    # Если все столбцы - часть PK, ничего не делаем при конфликте
                    insert_query += f' ON CONFLICT ({pk_columns_str}) DO NOTHING'

            # Выполняем запрос
            await conn.executemany(insert_query, [list(record.values()) for record in records])
    return True

def clean_value(val):
        try:
            import math
            if val is None:
                return None
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                return None
            return val
        except Exception:
            return val

@read_only_guard
async def upload_dicts_to_db(
    records: list[dict],
    schema: str,
    table_name: str,
    username: str,
    password: str,
    update_on_pk: bool = True,
) -> bool:
    """
    Загружает данные из списка словарей в существующую таблицу в базе данных.
    Если update_on_pk=True, выполняет UPSERT по первичному ключу (INSERT ON CONFLICT UPDATE).
    Требует, чтобы все словари имели одинаковые ключи, соответствующие столбцам таблицы.
    Таблица должна быть создана заранее.
    Не использует pandas.
    """
    if not records:
        return True
    columns = list(records[0].keys())
    # Преобразуем NaN/None/inf в None вручную
    
    records_clean = [
        {k: clean_value(v) for k, v in rec.items()} for rec in records
    ]
    async with get_connection(username, password) as conn:
        pk_columns = []
        if update_on_pk:
            pk_columns = await _get_pk_columns(conn, schema, table_name)
            if pk_columns and not all(col in columns for col in pk_columns):
                missing_cols = [col for col in pk_columns if col not in columns]
                raise ValueError(
                    f"Словари не содержат столбцы первичного ключа {missing_cols}, необходимые для update_on_pk."
                )
        columns_str = ', '.join([f'"{col}"' for col in columns])
        values_template = ', '.join([f'${i+1}' for i in range(len(columns))])
        insert_query = f'INSERT INTO "{schema}"."{table_name}" ({columns_str}) VALUES ({values_template})'
        if update_on_pk and pk_columns:
            pk_columns_str = ', '.join([f'"{col}"' for col in pk_columns])
            update_cols = [col for col in columns if col not in pk_columns]
            if update_cols:
                update_set_str = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in update_cols])
                insert_query += f' ON CONFLICT ({pk_columns_str}) DO UPDATE SET {update_set_str}'
            else:
                insert_query += f' ON CONFLICT ({pk_columns_str}) DO NOTHING'
        await conn.executemany(insert_query, [list(rec.values()) for rec in records_clean])
    return True

# --- Предпросмотр таблицы с лимитом строк ---
async def get_table_rows(
    schema: str, table_name: str, username: str, password: str, limit: int | None = None
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
        valid_tables = await conn.fetch(valid_tables_query, schema)
        valid_table_names = {row["tablename"] for row in valid_tables}

        if table_name not in valid_table_names:
            raise ValueError(f"Таблица '{table_name}' не найдена или недоступна в схеме '{schema}'.")

        # Формируем SQL-запрос
        if limit is not None:
            if not (1 <= limit <= 10**10): # Разумный диапазон для лимита
                raise ValueError("Значение лимита вне допустимого диапазона. Должно быть от 1 до 10^10.")
            query = f'SELECT * FROM "{schema}"."{table_name}" LIMIT {limit}'
        else:
            query = f'SELECT * FROM "{schema}"."{table_name}"'

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
            WHERE schemaname = $1
            AND has_table_privilege(current_user, concat(schemaname, '.', tablename), 'SELECT')
        """
        tables = await conn.fetch(query, settings.SCHEMA)
        return [record['tablename'] for record in tables]


# --- Получение доступных пользователю таблиц по всем схемам ---
async def get_user_table_names_by_schema(username: str, password: str) -> dict:
    """
    Возвращает словарь {schema: [table1, table2, ...]} с таблицами, к которым пользователь имеет SELECT.
    """
    async with get_connection(username, password) as conn:
        # Получаем все схемы, кроме служебных
        schemas_query = """
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        """
        schemas = await conn.fetch(schemas_query)
        result = {}
        for row in schemas:
            schema = row['schema_name']
            tables_query = f'''
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = $1
                AND has_table_privilege(current_user, concat(schemaname, '.', tablename), 'SELECT')
            '''
            tables = await conn.fetch(tables_query, schema)
            table_names = [record['tablename'] for record in tables]
            result[schema] = table_names  # всегда добавляем схему, даже если список пустой
        return result

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

# --- Проверка БД и DF на соответствие столбцов ---
async def check_df_matches_table_schema(df: pd.DataFrame, schema: str, table_name: str, username: str, password: str) -> bool:
    """
    Проверяет, соответствует ли структура DataFrame структуре таблицы в базе данных.
    """
    try:
        async with get_connection(username, password) as conn:
            # Проверяем существование таблицы
            check_query = """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = $1 AND table_name = $2
                )
            """
            exists = await conn.fetchval(check_query, schema, table_name)
            if not exists:
                return False
            
            # Получаем информацию о столбцах таблицы
            columns_query = """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """
            db_columns = await conn.fetch(columns_query, schema, table_name)
            
            db_schema = {row['column_name'].lower(): PG_TO_PD_TYPE_MAP.get(row['data_type'].lower(), 'object')
                         for row in db_columns}
            
            df_columns_lower = set(col.lower() for col in df.columns)
            db_columns_lower = set(db_schema.keys())
            
            if not df_columns_lower.issubset(db_columns_lower):
                return False
            for col in df.columns:
                df_type = str(df[col].dtype)
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df_type = 'datetime64[ns]'
                    
                expected_type = db_schema.get(col.lower())
                
                if expected_type is None: # Столбец в DF есть, но нет в схеме БД
                    return False

                # Проверяем совместимость типов
                if df_type != expected_type and not (
                    (df_type.startswith('int') and expected_type == 'int64') or
                    (df_type.startswith('float') and expected_type == 'float64') or
                    (df_type in ('object', 'string') and expected_type == 'object') or
                    (df_type.startswith('int') and expected_type == 'float64')
                ):
                    return False
            
            return True
            
    except Exception as e:
        # Логируем исключение для отладки
        print(f"Ошибка при проверке соответствия схемы DataFrame: {e}")
        return False

# --- Получение количества всех таблиц в схеме ---
async def get_total_table_count(username: str, password: str) -> int:
    """
    Возвращает количество всех таблиц в схеме (для текущей БД).
    """
    async with get_connection(username, password) as conn:
        query = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = $1
        """
        count = await conn.fetchval(query, settings.SCHEMA)
        return count

# --- Получение количества всех таблиц по всем схемам ---
async def get_total_table_count_by_schema(username: str, password: str) -> dict:
    """
    Возвращает словарь {schema: count} с количеством таблиц в каждой схеме.
    """
    async with get_connection(username, password) as conn:
        schemas_query = """
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
        """
        schemas = await conn.fetch(schemas_query)
        result = {}
        for row in schemas:
            schema = row['schema_name']
            count_query = '''
                SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = $1
            '''
            count = await conn.fetchval(count_query, schema)
            result[schema] = count
        return result