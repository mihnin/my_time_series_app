import io
import pandas as pd
from datetime import timedelta
import os
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from .jwt_logic import create_access_token, get_current_user_db_creds
from sessions.utils import get_session_path
import json
from .model import DBConnectionRequest, DBConnectionResponse, EnvUpdateRequest, EnvUpdateResponse, EnvVarsResponse, SecretKeyRequest, TablesResponse
from .settings import settings
from .env_utils import validate_secret_key, update_env_variables
from .db_manager import (
    get_user_table_names,
    get_table_rows,
    create_table_from_df,  # добавлено
    upload_df_to_db,
    check_db_connection,
)

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
    Возвращает список таблиц из БД, к которым текущий пользователь имеет привилегию SELECT.
    """
    try:
        table_names = await get_user_table_names(db_creds["username"], db_creds["password"])
        return TablesResponse(success=True, tables=table_names)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tables: {str(e)}")


@router.post('/get-table-preview')
async def get_table_preview(
    payload: dict,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Возвращает первые 10 строк из указанной таблицы (для предпросмотра).
    Тело запроса: {"table": "название_таблицы"}
    """
    table_name = payload.get("table")
    if not table_name:
        raise HTTPException(status_code=400, detail="Table name is required")

    try:
        # Используем get_table_rows с лимитом
        result = await get_table_rows(table_name, db_creds['username'], db_creds['password'], 10)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid table name or limit: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview table: {str(e)}")


@router.post('/upload-excel-to-db')
async def upload_excel_to_db_endpoint(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    primary_keys: str = Form(None),  # Новое поле
    dbSaveMode: str = Form('new'),   # Новое поле: режим сохранения
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Загружает Excel-файл в новую таблицу или в существующую (по выбору пользователя).
    Если таблица уже существует и выбран режим 'new', будет ошибка.
    Если выбран режим 'existing', пытается загрузить в существующую таблицу.
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
            await create_table_from_df(df, table_name, db_creds['username'], db_creds['password'], primary_keys=pk_list)
            await upload_df_to_db(df, table_name, db_creds['username'], db_creds['password'])
            return {"success": True, "detail": f"Таблица '{table_name}' успешно загружена."}
        else:
            # Пытаемся загрузить в существующую таблицу
            try:
                await upload_df_to_db(df, table_name, db_creds['username'], db_creds['password'])
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
    payload: dict,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Возвращает все данные из указанной таблицы (для загрузки в приложение).
    Тело запроса: {"table": "название_таблицы"}
    """
    table_name = payload.get("table")
    if not table_name:
        raise HTTPException(status_code=400, detail="Table name is required")

    try:
        # Используем get_table_rows без лимита для скачивания всех данных
        result = await get_table_rows(table_name, db_creds['username'], db_creds['password'])
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки таблицы: {str(e)}")


@router.post('/save-prediction-to-db')
async def save_prediction_to_db(
    payload: dict,
    db_creds: dict = Depends(get_current_user_db_creds)
):
    """
    Сохраняет прогноз (prediction_{session_id}.xlsx) из папки training_sessions/{session_id}/ в БД.
    Тело запроса: {"session_id": ..., "table_name": ..., "create_new": true/false}
    """
    session_id = payload.get("session_id")
    table_name = payload.get("table_name")
    create_new = payload.get("create_new", False)
    if not session_id or not table_name:
        raise HTTPException(status_code=400, detail="session_id и table_name обязательны")
    # Получаем путь к сессии через get_session_path
    session_path = get_session_path(session_id)
    pred_path = os.path.join(session_path, f"prediction_{session_id}.xlsx")
    if not os.path.exists(pred_path):
        raise HTTPException(status_code=404, detail=f"Файл прогноза не найден: {pred_path}")
    try:
        df = pd.read_excel(pred_path)
        # Удаляем колонки '0.1', '0.2', ..., '0.9' если они есть
        drop_cols = [str(round(x/10, 1)) for x in range(1, 10)]
        df = df.drop(columns=[col for col in drop_cols if col in df.columns], errors='ignore')
        if df.empty:
            raise HTTPException(status_code=400, detail="Файл прогноза пустой")
        if create_new:
            # Создать новую таблицу и загрузить данные
            await create_table_from_df(df, table_name, db_creds['username'], db_creds['password'])
            await upload_df_to_db(df, table_name, db_creds['username'], db_creds['password'])
        else:
            # Загрузить в существующую таблицу
            await upload_df_to_db(df, table_name, db_creds['username'], db_creds['password'])
        return {"success": True, "detail": f"Прогноз успешно сохранён в таблицу '{table_name}'"}
    except HTTPException as e:
        raise e
    except Exception as e:
        if "уже существует" in str(e) or "already exists" in str(e):
            raise HTTPException(status_code=409, detail=f"Ошибка: Таблица '{table_name}' уже существует. Пожалуйста, выберите другое имя.")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения прогноза в БД: {str(e)}")