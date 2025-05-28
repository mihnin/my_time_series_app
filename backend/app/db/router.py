import io
import pandas as pd
from datetime import timedelta
import os
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import json
from .jwt_logic import create_access_token, get_current_user_db_creds
from sessions.utils import get_session_path
from .model import (
    DBConnectionRequest, DBConnectionResponse, EnvUpdateRequest, EnvUpdateResponse, EnvVarsResponse, SecretKeyRequest, TablesResponse,
    TablePreviewRequest, DownloadTableRequest, SavePredictionRequest, CreateTableFromFileRequest, CheckDFMatchesTableSchemaRequest
)
from .settings import settings
from .env_utils import validate_secret_key, update_env_variables
from .db_manager import (
    get_user_table_names_by_schema,
    get_table_rows,
    create_table_from_df,
    upload_df_to_db,
    check_db_connection,
    check_df_matches_table_schema,
    get_total_table_count_by_schema
)
import logging

router = APIRouter()



@router.post('/validate-secret-key', response_model=EnvVarsResponse)
async def validate_key(request: SecretKeyRequest):
    """
    Проверяет переданный секретный ключ на соответствие с SECRET_KEY из настроек.
    Если ключ верный, возвращает также текущие значения переменных окружения.
    """
    if validate_secret_key(request.secret_key):
        # Возвращаем текущие значения переменных окружения
        env_vars = {
            "DB_USER": settings.DB_USER,
            "DB_PASS": settings.DB_PASS,
            "DB_HOST": settings.DB_HOST,
            "DB_PORT": settings.DB_PORT,
            "DB_NAME": settings.DB_NAME,
            "DB_SCHEMA": settings.SCHEMA
        }
        return EnvVarsResponse(success=True, message="Секретный ключ верный", db_vars=env_vars)
    return EnvVarsResponse(success=False, message="Неверный секретный ключ")


@router.post('/update-env-variables', response_model=EnvUpdateResponse)
async def update_env_vars(request: EnvUpdateRequest):
    """
    Обновляет переменные окружения в файле .env, если указан правильный секретный ключ.
    """
    if not validate_secret_key(request.secret_key):
        return EnvUpdateResponse(success=False, message="Неверный секретный ключ")
    
    # Создаем словарь с переменными окружения
    env_vars = {
        "DB_USER": request.DB_USER,
        "DB_PASS": request.DB_PASS,
        "DB_HOST": request.DB_HOST,
        "DB_PORT": request.DB_PORT,
        "DB_NAME": request.DB_NAME,
        "DB_SCHEMA": request.DB_SCHEMA,
    }
    
    # Обновляем переменные окружения
    success = await update_env_variables(env_vars)
    if success:
        return EnvUpdateResponse(success=True, message="Переменные окружения успешно обновлены")
    return EnvUpdateResponse(success=False, message="Не удалось обновить переменные окружения")

@router.post('/login', response_model=DBConnectionResponse)
async def login_for_access_token(data: DBConnectionRequest):
    """
    Эндпоинт для аутентификации пользователя БД и выдачи JWT токена.
    """
    is_connected = await check_db_connection(data.username, data.password)
    if not is_connected:
        return DBConnectionResponse(success=False, detail="Authentication failed: Invalid credentials")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": data.username, "password": data.password},
        expires_delta=access_token_expires
    )
    return DBConnectionResponse(success=True, detail="Connection successful, token issued", access_token=access_token)


@router.get('/get-tables', response_model=TablesResponse)
async def get_tables(db_creds: dict = Depends(get_current_user_db_creds)):
    """
    Возвращает словарь {schema: [таблицы]} и количество таблиц по схемам.
    """
    try:
        user_tables = await get_user_table_names_by_schema(db_creds["username"], db_creds["password"])
        # Получаем количество всех таблиц под суперпользователем
        total_counts = await get_total_table_count_by_schema(settings.SUPERUSER_DB_USER, settings.SUPERUSER_DB_PASS)
        count_available = sum(len(tables) for tables in user_tables.values())
        count_total = sum(total_counts.values())
        return TablesResponse(success=True, tables=user_tables, count_available=count_available, count_total=count_total)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tables: {str(e)}")


@router.post('/get-table-preview')
async def get_table_preview(
    req: TablePreviewRequest,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Возвращает первые 10 строк из указанной таблицы (для предпросмотра).
    Тело запроса: {"schema": ..., "table": ...}
    """
    schema = req.schema
    table_name = req.table
    if not schema or not table_name:
        raise HTTPException(status_code=400, detail="Schema and table name are required")
    try:
        result = await get_table_rows(schema, table_name, db_creds['username'], db_creds['password'], 5)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid table name or limit: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview table: {str(e)}")


@router.post('/upload-excel-to-db')
async def upload_excel_to_db_endpoint(
    file: UploadFile = File(...),
    schema: str = Form(...),
    table_name: str = Form(...),
    primary_keys: str = Form(None),
    dbSaveMode: str = Form('new'),
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Загружает Excel-файл в новую таблицу или в существующую (по выбору пользователя).
    """
    try:
        if not (file.filename and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls'))):
            raise HTTPException(status_code=400, detail='Файл должен быть Excel (.xlsx или .xls)')

        content = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'Ошибка чтения Excel: {str(e)}')

        if df.empty:
            raise HTTPException(status_code=400, detail='Файл пустой или не содержит данных')

        # Парсим первичные ключи
        pk_list = []
        if primary_keys:
            try:
                pk_list = json.loads(primary_keys)
                if not isinstance(pk_list, list):
                    pk_list = []
            except Exception:
                pk_list = []
        if dbSaveMode == 'new':
            # Сначала создаём таблицу, затем загружаем данные
            await create_table_from_df(df, schema, table_name, db_creds['username'], db_creds['password'], primary_keys=pk_list)
            await upload_df_to_db(df, schema, table_name, db_creds['username'], db_creds['password'])
            return {"success": True, "detail": f"Таблица '{table_name}' успешно загружена."}
        else:
            # Проверяем соответствие схемы перед загрузкой в существующую таблицу
            
            matches = await check_df_matches_table_schema(df, schema, table_name, db_creds['username'], db_creds['password'])
            if not matches:
                return {"success": False, "detail": f"Структура DataFrame не совпадает со структурой таблицы '{table_name}' в БД. Проверьте названия и типы столбцов."}
            try:
                await upload_df_to_db(df, schema, table_name, db_creds['username'], db_creds['password'])
                return {"success": True, "detail": f"Данные успешно загружены в таблицу '{table_name}'."}
            except Exception as e:
                return {"success": False, "detail": f"Ошибка при загрузке в существующую таблицу: {str(e)}"}
    except HTTPException as e:
        raise e
    except Exception as e:
        if "уже существует" in str(e) or "already exists" in str(e):
            raise HTTPException(status_code=409, detail=f"Ошибка: Таблица '{table_name}' уже существует. Пожалуйста, выберите другое имя.")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки файла в БД: {str(e)}")


@router.post('/download-table-from-db')
async def download_table_from_db_endpoint(
    req: DownloadTableRequest,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Возвращает все данные из указанной таблицы в виде Excel-файла.
    Тело запроса: {"schema": ..., "table": ...}
    """
    schema = req.schema
    table_name = req.table
    if not schema or not table_name:
        raise HTTPException(status_code=400, detail="Schema and table name are required")
    try:
        result = await get_table_rows(schema, table_name, db_creds['username'], db_creds['password'])
        if not result or len(result) == 0:
            raise HTTPException(status_code=404, detail=f"Таблица '{table_name}' пуста или не найдена")
        df = pd.DataFrame(result)
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        logging.info(f"[download-table-from-db] Таблица '{table_name}' успешно выгружена в Excel.")
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={table_name}.xlsx"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки таблицы: {str(e)}")


@router.post('/save-prediction-to-db')
async def save_prediction_to_db(
    req: SavePredictionRequest,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Сохраняет прогноз (prediction_{session_id}.xlsx) из папки training_sessions/{session_id}/ в БД.
    Тело запроса: {"schema": ..., "session_id": ..., "table_name": ..., "create_new": true/false}
    """
    schema = req.schema
    session_id = req.session_id
    table_name = req.table_name
    create_new = req.create_new
    if not schema or not session_id or not table_name:
        raise HTTPException(status_code=400, detail="schema, session_id и table_name обязательны")
    session_path = get_session_path(session_id)
    pred_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    if not os.path.exists(pred_path):
        raise HTTPException(status_code=404, detail=f"Файл прогноза не найден: {pred_path}")
    try:
        df = pd.read_excel(pred_path)
        drop_cols = [str(round(x/10, 1)) for x in range(1, 10)]
        df = df.drop(columns=[col for col in drop_cols if col in df.columns], errors='ignore')
        if df.empty:
            raise HTTPException(status_code=400, detail="Файл прогноза пустой")
        if create_new:
            await create_table_from_df(df, schema, table_name, db_creds['username'], db_creds['password'])
            await upload_df_to_db(df, schema, table_name, db_creds['username'], db_creds['password'])
        else:
            matches = await check_df_matches_table_schema(df, schema, table_name, db_creds['username'], db_creds['password'])
            if not matches:
                raise HTTPException(status_code=400, detail=f"Структура DataFrame не совпадает со структурой таблицы '{table_name}' в БД. Проверьте названия и типы столбцов.")
            await upload_df_to_db(df, schema, table_name, db_creds['username'], db_creds['password'])
        return {"success": True, "detail": f"Прогноз успешно сохранён в таблицу '{table_name}'"}
    except HTTPException as e:
        raise e
    except Exception as e:
        if "уже существует" in str(e) or "already exists" in str(e):
            raise HTTPException(status_code=409, detail=f"Ошибка: Таблица '{table_name}' уже существует. Пожалуйста, выберите другое имя.")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения прогноза в БД: {str(e)}")


@router.post('/create-table-from-file')
async def create_table_from_file_endpoint(
    file: UploadFile = File(...),
    schema: str = Form(...),
    table_name: str = Form(...),
    primary_keys: str = Form(None),
    create_table_only: str = Form('false'),
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Создает таблицу в БД по первой строке файла (Excel/CSV). Если таблица уже есть — ошибка.
    Используется только первая строка данных (после заголовков).
    """
    try:
        print(file.filename)
        if not (file.filename and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls'))):
            raise HTTPException(status_code=400, detail='Файл должен быть Excel (.xlsx или .xls)')
        content = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'Ошибка чтения Excel: {str(e)}')
        if df.empty:
            raise HTTPException(status_code=400, detail='Файл пустой или не содержит данных')
        # Берём только первую строку (после заголовков)
        df_first = df.head(1)
        # Парсим первичные ключи
        pk_list = []
        if primary_keys:
            try:
                pk_list = json.loads(primary_keys)
                if not isinstance(pk_list, list):
                    pk_list = []
            except Exception:
                pk_list = []
        # Проверяем, есть ли таблица
        try:
            await create_table_from_df(df_first, schema, table_name, db_creds['username'], db_creds['password'], primary_keys=pk_list)
        except Exception as e:
            if "уже существует" in str(e) or "already exists" in str(e):
                return {"success": False, "detail": f"Ошибка: Таблица '{table_name}' уже существует. Пожалуйста, выберите другое имя."}
            raise
        return {"success": True, "detail": f"Таблица '{table_name}' успешно создана по первой строке файла."}
    except Exception as e:
        if "уже существует" in str(e) or "already exists" in str(e):
            return {"success": False, "detail": f"Ошибка: Таблица '{table_name}' уже существует. Пожалуйста, выберите другое имя."}
        raise HTTPException(status_code=500, detail=f"Ошибка создания таблицы: {str(e)}")


@router.post('/check-df-matches-table-schema')
async def check_df_matches_table_schema_endpoint(
    file: UploadFile = File(...),
    schema: str = Form(...),
    table_name: str = Form(...),
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Проверяет, совпадает ли структура загруженного файла (Excel) со структурой выбранной таблицы в БД.
    Возвращает {success: True/False, detail: ...}
    """
    try:
        if not (file.filename and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls'))):
            raise HTTPException(status_code=400, detail='Файл должен быть Excel (.xlsx или .xls)')
        content = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f'Ошибка чтения Excel: {str(e)}')
        if df.empty:
            raise HTTPException(status_code=400, detail='Файл пустой или не содержит данных')
        matches = await check_df_matches_table_schema(df, schema, table_name, db_creds['username'], db_creds['password'])
        if matches:
            return {"success": True, "detail": "Структура совпадает"}
        else:
            return {"success": False, "detail": "Структура файла не совпадает с таблицей в БД"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка проверки структуры: {str(e)}")