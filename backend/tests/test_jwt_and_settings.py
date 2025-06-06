import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../app')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend/app')))

import pytest
from backend.app.db import jwt_logic, env_utils, settings
from datetime import timedelta
from jose import jwt, JWTError

# --- JWT Logic ---
def test_jwt_token_expiry():
    data = {'sub': 'user', 'password': 'pass'}
    token = jwt_logic.create_access_token(data, expires_delta=timedelta(seconds=1))
    decoded = jwt.decode(token, settings.settings.SECRET_KEY, algorithms=[settings.settings.ALGORITHM])
    assert 'exp' in decoded
    # Проверяем, что exp - это int (timestamp)
    assert isinstance(decoded['exp'], int) or isinstance(decoded['exp'], float)


def test_jwt_token_invalid_signature():
    data = {'sub': 'user', 'password': 'pass'}
    token = jwt_logic.create_access_token(data)
    # Подделываем секрет
    with pytest.raises(JWTError):
        jwt.decode(token, 'wrong_secret', algorithms=[settings.settings.ALGORITHM])


def test_jwt_token_missing_fields():
    data = {'foo': 'bar'}
    token = jwt_logic.create_access_token(data)
    decoded = jwt.decode(token, settings.settings.SECRET_KEY, algorithms=[settings.settings.ALGORITHM])
    # sub и password должны отсутствовать
    assert 'sub' not in decoded or decoded['sub'] is None
    assert 'password' not in decoded or decoded['password'] is None

# --- env_utils: validate_secret_key edge cases ---
def test_validate_secret_key_empty():
    assert env_utils.validate_secret_key('') is False

def test_validate_secret_key_none():
    assert env_utils.validate_secret_key(None) is False

# --- settings: проверка свойств ---
def test_settings_properties():
    s = settings.settings
    # Просто проверяем, что свойства возвращают строки (или пусто)
    assert isinstance(s.DB_USER, str)
    assert isinstance(s.DB_PASS, str)
    assert isinstance(s.DB_HOST, str)
    assert isinstance(s.DB_PORT, str)
    assert isinstance(s.DB_NAME, str)
    assert isinstance(s.SCHEMA, str)
    assert isinstance(s.SECRET_KEY, str)
    assert isinstance(s.sqlalchemy_url, str)
    assert isinstance(s.asyncpg_url, str)
    assert isinstance(s.SUPERUSER_DB_USER, str)
    assert isinstance(s.SUPERUSER_DB_PASS, str)
