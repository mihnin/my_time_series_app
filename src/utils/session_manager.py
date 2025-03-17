# src/utils/session_manager.py
import streamlit as st
import time
import json
import pickle
import logging
import os
import hashlib
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Максимальный срок жизни сессии (в часах)
SESSION_TTL = 24

# Путь для сохранения данных сессии
SESSION_DIR = "data/sessions"

class SessionManager:
    """Менеджер сессий пользователей, обеспечивающий сохранение состояния"""
    _instance = None
    
    def __new__(cls):
        # Паттерн Singleton для доступа к единому экземпляру
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
            
        # Инициализация при первом создании
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_last_access: Dict[str, float] = {}
        self._ensure_session_dir()
        self._initialized = True
        logging.info("Менеджер сессий инициализирован")
    
    def _ensure_session_dir(self) -> None:
        """Создает директорию для хранения сессий, если её нет"""
        if not os.path.exists(SESSION_DIR):
            os.makedirs(SESSION_DIR, exist_ok=True)
            logging.info(f"Создана директория для сессий: {SESSION_DIR}")
    
    def get_or_create_session_id(self) -> str:
        """Получает существующий ID сессии или создает новый"""
        # Проверяем существующую сессию в Streamlit
        if 'session_id' not in st.session_state:
            # Создаем новый уникальный ID сессии
            session_id = str(uuid.uuid4())
            st.session_state['session_id'] = session_id
            logging.info(f"Создана новая сессия: {session_id}")
        
        return st.session_state['session_id']
    
    def save(self, key: str, value: Any, session_id: Optional[str] = None) -> None:
        """Сохраняет значение в сессии по ключу"""
        if session_id is None:
            session_id = self.get_or_create_session_id()
        
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        
        self._sessions[session_id][key] = value
        self._session_last_access[session_id] = time.time()
        
        # Сохраняем файл сессии (если это не объект, который нельзя сериализовать)
        try:
            self._persist_session(session_id)
        except Exception as e:
            logging.warning(f"Не удалось сохранить сессию {session_id}: {e}")
    
    def get(self, key: str, default: Any = None, session_id: Optional[str] = None) -> Any:
        """Получает значение из сессии по ключу"""
        if session_id is None:
            session_id = self.get_or_create_session_id()
        
        # Обновляем время последнего доступа
        self._session_last_access[session_id] = time.time()
        
        # Если сессия не загружена, пытаемся загрузить из файла
        if session_id not in self._sessions:
            self._load_session(session_id)
        
        # Возвращаем значение или default
        return self._sessions.get(session_id, {}).get(key, default)
    
    def delete(self, key: str, session_id: Optional[str] = None) -> None:
        """Удаляет значение из сессии по ключу"""
        if session_id is None:
            session_id = self.get_or_create_session_id()
        
        if session_id in self._sessions and key in self._sessions[session_id]:
            del self._sessions[session_id][key]
            self._session_last_access[session_id] = time.time()
            self._persist_session(session_id)
    
    def clear(self, session_id: Optional[str] = None) -> None:
        """Очищает всю сессию"""
        if session_id is None:
            session_id = self.get_or_create_session_id()
        
        if session_id in self._sessions:
            self._sessions[session_id] = {}
            self._session_last_access[session_id] = time.time()
            
            # Удаляем файл сессии, если он существует
            session_file = self._get_session_file_path(session_id)
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    logging.info(f"Удален файл сессии: {session_file}")
                except Exception as e:
                    logging.error(f"Ошибка при удалении файла сессии {session_file}: {e}")
    
    def _get_session_file_path(self, session_id: str) -> str:
        """Возвращает путь к файлу сессии"""
        # Используем SHA-256 для создания безопасного имени файла
        hashed_id = hashlib.sha256(session_id.encode()).hexdigest()
        return os.path.join(SESSION_DIR, f"session_{hashed_id}.pkl")
    
    def _persist_session(self, session_id: str) -> None:
        """Сохраняет сессию в файл для постоянного хранения"""
        if session_id not in self._sessions:
            return
        
        session_file = self._get_session_file_path(session_id)
        
        try:
            # Создаем копию для сериализации, исключая несериализуемые объекты
            serializable_session = {}
            for key, value in self._sessions[session_id].items():
                try:
                    # Проверяем, можно ли сериализовать
                    pickle.dumps(value)
                    serializable_session[key] = value
                except (pickle.PickleError, TypeError):
                    logging.warning(f"Объект с ключом '{key}' не может быть сериализован")
            
            # Сохраняем только сериализуемые данные
            with open(session_file, 'wb') as f:
                pickle.dump(serializable_session, f)
        except Exception as e:
            logging.error(f"Ошибка при сохранении сессии {session_id}: {e}")
    
    def _load_session(self, session_id: str) -> None:
        """Загружает сессию из файла"""
        session_file = self._get_session_file_path(session_id)
        
        if not os.path.exists(session_file):
            # Если файла нет, создаем пустую сессию
            self._sessions[session_id] = {}
            return
        
        try:
            with open(session_file, 'rb') as f:
                session_data = pickle.load(f)
                self._sessions[session_id] = session_data
                logging.info(f"Загружена сессия из файла: {session_id}")
        except Exception as e:
            logging.error(f"Ошибка при загрузке сессии {session_id}: {e}")
            # В случае ошибки создаем пустую сессию
            self._sessions[session_id] = {}
    
    def cleanup_old_sessions(self) -> int:
        """Удаляет старые сессии, которые не использовались долгое время"""
        now = time.time()
        ttl_seconds = SESSION_TTL * 3600  # TTL в секундах
        removed_count = 0
        
        # Проверяем активные сессии в памяти
        for session_id in list(self._session_last_access.keys()):
            last_access = self._session_last_access[session_id]
            
            if now - last_access > ttl_seconds:
                # Удаляем из памяти
                if session_id in self._sessions:
                    del self._sessions[session_id]
                
                del self._session_last_access[session_id]
                
                # Удаляем файл сессии
                session_file = self._get_session_file_path(session_id)
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                    except Exception as e:
                        logging.error(f"Ошибка при удалении файла сессии {session_file}: {e}")
                
                removed_count += 1
        
        # Проверяем файлы сессий на диске
        if os.path.exists(SESSION_DIR):
            for filename in os.listdir(SESSION_DIR):
                if filename.startswith("session_") and filename.endswith(".pkl"):
                    file_path = os.path.join(SESSION_DIR, filename)
                    
                    # Получаем время последней модификации файла
                    try:
                        mtime = os.path.getmtime(file_path)
                        if now - mtime > ttl_seconds:
                            os.remove(file_path)
                            removed_count += 1
                    except Exception as e:
                        logging.error(f"Ошибка при проверке/удалении файла {file_path}: {e}")
        
        if removed_count > 0:
            logging.info(f"Удалено {removed_count} старых сессий")
        
        return removed_count

# Глобальная функция для доступа к экземпляру менеджера сессий
def get_session_manager() -> SessionManager:
    """Возвращает экземпляр менеджера сессий (синглтон)"""
    return SessionManager()

# Функции-помощники для упрощенного доступа
def save_to_session(key: str, value: Any) -> None:
    """Сохраняет значение в текущей сессии по ключу"""
    get_session_manager().save(key, value)

def get_from_session(key: str, default: Any = None) -> Any:
    """Получает значение из текущей сессии по ключу"""
    return get_session_manager().get(key, default)

def delete_from_session(key: str) -> None:
    """Удаляет значение из текущей сессии по ключу"""
    get_session_manager().delete(key)

def clear_session() -> None:
    """Очищает текущую сессию"""
    get_session_manager().clear()

def get_current_session_id() -> str:
    """Возвращает ID текущей сессии"""
    return get_session_manager().get_or_create_session_id() 