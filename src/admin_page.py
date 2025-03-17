# src/admin_page.py
import streamlit as st
import yaml
import os
import hashlib
import time
import pandas as pd
import psutil
from datetime import datetime
import logging
from typing import Dict, Any

from src.utils.logger import read_logs, clear_logs
from src.utils.resource_monitor import get_resource_monitor
from src.utils.queue_manager import get_queue_manager, TaskStatus
from src.utils.session_manager import get_session_manager, SESSION_DIR
from src.config.app_config import get_config, reload_config

# Константы
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # В реальном приложении должен быть хеш пароля
CONFIG_PATH = "config/config.yaml"

def hash_password(password: str) -> str:
    """Хеширует пароль с использованием SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate() -> bool:
    """Проверяет аутентификацию пользователя"""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
        st.session_state.admin_login_attempts = 0
        st.session_state.admin_last_attempt = 0
    
    # Проверка блокировки после неудачных попыток
    current_time = time.time()
    if st.session_state.admin_login_attempts >= 5:
        time_passed = current_time - st.session_state.admin_last_attempt
        if time_passed < 300:  # 5 минут блокировки
            st.error(f"Слишком много неудачных попыток. Попробуйте через {int(300 - time_passed)} секунд.")
            return False
        else:
            st.session_state.admin_login_attempts = 0
    
    if not st.session_state.admin_authenticated:
        st.header("Вход в административную панель")
        
        username = st.text_input("Логин", key="admin_username")
        password = st.text_input("Пароль", type="password", key="admin_password")
        
        if st.button("Войти", key="admin_login_button"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.session_state.admin_login_attempts = 0
                st.success("Авторизация успешна!")
                st.rerun()  # Перезагружаем страницу, чтобы показать админ-панель
            else:
                st.session_state.admin_login_attempts += 1
                st.session_state.admin_last_attempt = current_time
                st.error("Неверный логин или пароль")
                
        return False
    
    return True

def save_config(config_data: Dict[str, Any]) -> bool:
    """Сохраняет конфигурацию в YAML-файл"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        # Перезагружаем конфигурацию
        reload_config()
        return True
    except Exception as e:
        logging.error(f"Ошибка при сохранении конфигурации: {e}")
        return False

def show_admin_page():
    """Отображает административную страницу"""
    st.title("Административная панель")
    
    if not authenticate():
        return
    
    # Если пользователь аутентифицирован, показываем админ-панель
    tabs = st.tabs(["Настройки системы", "Управление ресурсами", "Задачи", "Сессии", "Логи"])
    
    with tabs[0]:
        show_system_settings()
    
    with tabs[1]:
        show_resource_management()
    
    with tabs[2]:
        show_task_management()
    
    with tabs[3]:
        show_session_management()
    
    with tabs[4]:
        show_logs_management()

def show_system_settings():
    """Раздел настроек системы"""
    st.header("Настройки системы")
    
    # Загружаем текущую конфигурацию
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        st.error(f"Ошибка загрузки конфигурации: {e}")
        return
    
    st.subheader("Основные настройки")
    app_name = st.text_input("Название приложения", value=config_data.get("app_name", ""))
    app_version = st.text_input("Версия приложения", value=config_data.get("app_version", ""))
    debug_mode = st.checkbox("Режим отладки", value=config_data.get("debug_mode", False))
    
    st.subheader("Настройки ресурсов")
    resource_col1, resource_col2, resource_col3 = st.columns(3)
    
    with resource_col1:
        cpu_threshold = st.slider(
            "Порог CPU (%)", 
            min_value=50, 
            max_value=100, 
            value=int(config_data.get("resource", {}).get("cpu_threshold", 90))
        )
    
    with resource_col2:
        memory_threshold = st.slider(
            "Порог памяти (%)", 
            min_value=50, 
            max_value=100, 
            value=int(config_data.get("resource", {}).get("memory_threshold", 80))
        )
    
    with resource_col3:
        disk_threshold = st.slider(
            "Порог диска (%)", 
            min_value=50, 
            max_value=100, 
            value=int(config_data.get("resource", {}).get("disk_threshold", 95))
        )
    
    check_interval = st.slider(
        "Интервал проверки (сек)", 
        min_value=1, 
        max_value=60, 
        value=int(config_data.get("resource", {}).get("check_interval", 5))
    )
    
    st.subheader("Настройки очереди")
    queue_col1, queue_col2 = st.columns(2)
    
    with queue_col1:
        max_workers = st.slider(
            "Макс. кол-во рабочих потоков", 
            min_value=1, 
            max_value=10, 
            value=int(config_data.get("queue", {}).get("max_workers", 2))
        )
        
        max_task_age = st.number_input(
            "Макс. возраст задач (часов)", 
            min_value=1, 
            max_value=168, 
            value=int(config_data.get("queue", {}).get("max_task_age", 86400) / 3600)
        )
    
    with queue_col2:
        task_timeout = st.number_input(
            "Таймаут задачи (мин)", 
            min_value=1, 
            max_value=1440, 
            value=int(config_data.get("queue", {}).get("task_timeout", 3600) / 60)
        )
        
        clean_interval = st.number_input(
            "Интервал очистки (мин)", 
            min_value=1, 
            max_value=1440, 
            value=int(config_data.get("queue", {}).get("clean_interval", 3600) / 60)
        )
    
    st.subheader("Настройки сессий")
    session_col1, session_col2 = st.columns(2)
    
    with session_col1:
        session_ttl = st.number_input(
            "Время жизни сессии (часов)", 
            min_value=1, 
            max_value=168, 
            value=int(config_data.get("session", {}).get("session_ttl", 24))
        )
    
    with session_col2:
        session_clean_interval = st.number_input(
            "Интервал очистки сессий (мин)", 
            min_value=1, 
            max_value=1440, 
            value=int(config_data.get("session", {}).get("clean_interval", 3600) / 60)
        )
    
    st.subheader("Настройки логов")
    log_col1, log_col2 = st.columns(2)
    
    with log_col1:
        log_level = st.selectbox(
            "Уровень логирования", 
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].index(
                config_data.get("logging", {}).get("log_level", "INFO")
            )
        )
        
        max_log_size = st.number_input(
            "Макс. размер лог-файла (МБ)", 
            min_value=1, 
            max_value=100, 
            value=int(config_data.get("logging", {}).get("max_log_size", 10485760) / (1024 * 1024))
        )
    
    with log_col2:
        date_format = st.text_input(
            "Формат даты", 
            value=config_data.get("logging", {}).get("date_format", "%Y-%m-%d %H:%M:%S")
        )
        
        backup_count = st.number_input(
            "Кол-во резервных копий логов", 
            min_value=1, 
            max_value=20, 
            value=int(config_data.get("logging", {}).get("backup_count", 5))
        )
    
    st.subheader("Автоматическое определение параметров")
    auto_freq_enabled = st.checkbox(
        "Автоматическое определение частоты", 
        value=config_data.get("auto_detection", {}).get("frequency_enabled", True)
    )
    
    auto_fields_enabled = st.checkbox(
        "Автоматический выбор полей", 
        value=config_data.get("auto_detection", {}).get("fields_enabled", True)
    )
    
    # Сохранение изменений
    if st.button("Сохранить настройки", key="save_settings_btn"):
        # Обновляем конфигурацию
        config_data["app_name"] = app_name
        config_data["app_version"] = app_version
        config_data["debug_mode"] = debug_mode
        
        # Настройки ресурсов
        if "resource" not in config_data:
            config_data["resource"] = {}
        config_data["resource"]["cpu_threshold"] = float(cpu_threshold)
        config_data["resource"]["memory_threshold"] = float(memory_threshold)
        config_data["resource"]["disk_threshold"] = float(disk_threshold)
        config_data["resource"]["check_interval"] = int(check_interval)
        
        # Настройки очереди
        if "queue" not in config_data:
            config_data["queue"] = {}
        config_data["queue"]["max_workers"] = int(max_workers)
        config_data["queue"]["task_timeout"] = int(task_timeout * 60)  # в секундах
        config_data["queue"]["clean_interval"] = int(clean_interval * 60)  # в секундах
        config_data["queue"]["max_task_age"] = int(max_task_age * 3600)  # в секундах
        
        # Настройки сессий
        if "session" not in config_data:
            config_data["session"] = {}
        config_data["session"]["session_ttl"] = int(session_ttl)
        config_data["session"]["clean_interval"] = int(session_clean_interval * 60)  # в секундах
        
        # Настройки логов
        if "logging" not in config_data:
            config_data["logging"] = {}
        config_data["logging"]["log_level"] = log_level
        config_data["logging"]["date_format"] = date_format
        config_data["logging"]["max_log_size"] = int(max_log_size * 1024 * 1024)  # в байтах
        config_data["logging"]["backup_count"] = int(backup_count)
        
        # Настройки автоопределения
        if "auto_detection" not in config_data:
            config_data["auto_detection"] = {}
        config_data["auto_detection"]["frequency_enabled"] = auto_freq_enabled
        config_data["auto_detection"]["fields_enabled"] = auto_fields_enabled
        
        # Сохраняем конфигурацию
        if save_config(config_data):
            st.success("Настройки успешно сохранены!")
        else:
            st.error("Ошибка при сохранении настроек.")

def show_resource_management():
    """Раздел управления ресурсами"""
    st.header("Управление ресурсами")
    
    resource_monitor = get_resource_monitor()
    
    # Текущее состояние ресурсов
    st.subheader("Текущее состояние")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        cpu_usage = psutil.cpu_percent()
        st.metric("CPU", f"{cpu_usage:.1f}%", delta=f"{cpu_usage - resource_monitor.last_cpu:.1f}%")
        
    with col2:
        memory = psutil.virtual_memory()
        mem_used_percent = memory.percent
        st.metric("Память", f"{mem_used_percent:.1f}%", delta=f"{mem_used_percent - resource_monitor.last_memory:.1f}%")
        
    with col3:
        disk = psutil.disk_usage('/')
        disk_used_percent = disk.percent
        st.metric("Диск", f"{disk_used_percent:.1f}%", delta=f"{disk_used_percent - resource_monitor.last_disk:.1f}%")
    
    # График истории использования ресурсов
    if hasattr(resource_monitor, 'history'):
        st.subheader("История использования ресурсов")
        history_df = pd.DataFrame(resource_monitor.history)
        if not history_df.empty:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], unit='s')
            
            st.line_chart(
                history_df.set_index('timestamp')[['cpu_percent', 'memory_percent', 'disk_percent']]
            )
    
    # Очистка ресурсов
    st.subheader("Очистка ресурсов")
    
    if st.button("Очистить кэш приложения", key="clear_app_cache"):
        import gc
        st.cache_data.clear()
        gc.collect()
        st.success("Кэш приложения очищен!")
    
    if st.button("Очистить временные файлы", key="clear_temp_files"):
        import tempfile
        import shutil
        try:
            temp_dir = tempfile.gettempdir()
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if item.startswith('streamlit') or item.startswith('st_'):
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except:
                        pass
            st.success("Временные файлы очищены!")
        except Exception as e:
            st.error(f"Ошибка при очистке временных файлов: {e}")

def show_task_management():
    """Раздел управления задачами"""
    st.header("Управление задачами")
    
    queue_manager = get_queue_manager()
    
    # Показать текущие задачи
    st.subheader("Текущие задачи")
    
    with st.container():
        tasks = []
        for task_id, task in queue_manager.tasks.items():
            tasks.append({
                'ID': task.id[:8],  # Показываем только первые 8 символов для краткости
                'Сессия': task.session_id[:8],
                'Статус': task.status.name,
                'Приоритет': task.priority.name,
                'Создана': datetime.fromtimestamp(task.created_at).strftime('%H:%M:%S'),
                'Прогресс': f"{task.progress * 100:.0f}%",
                'Длительность': f"{time.time() - task.started_at:.1f}с" if task.started_at else "-"
            })
        
        if tasks:
            tasks_df = pd.DataFrame(tasks)
            st.dataframe(tasks_df)
        else:
            st.info("Нет активных задач")
    
    # Очистка задач
    st.subheader("Действия")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Очистить завершенные задачи", key="clear_completed_tasks"):
            count = queue_manager.clean_completed_tasks(max_age_seconds=0)  # Удаляем все завершенные
            st.success(f"Очищено {count} завершенных задач")
    
    with col2:
        if st.button("Отменить все задачи в очереди", key="cancel_all_tasks"):
            count = 0
            for task_id, task in queue_manager.tasks.items():
                if task.status == TaskStatus.QUEUED:
                    if queue_manager.cancel_task(task_id):
                        count += 1
            st.success(f"Отменено {count} задач из очереди")

def show_session_management():
    """Показывает интерфейс управления сессиями пользователей"""
    st.header("Управление сессиями пользователей")
    
    session_manager = get_session_manager()
    
    # Показать текущие сессии
    st.subheader("Активные сессии")
    
    sessions = []
    
    # Получаем список всех файлов сессий в директории
    session_dir = getattr(session_manager, 'SESSION_DIR', SESSION_DIR)
    if not os.path.exists(session_dir):
        st.info("Директория сессий не существует.")
        return
    
    # Получаем данные о сессиях из внутреннего словаря
    for session_id, session_data in session_manager._sessions.items():
        last_access_time = session_manager._session_last_access.get(session_id, 0)
        # Определяем примерное время создания (используем время последнего доступа, если создание неизвестно)
        created_at = last_access_time  # Точное время создания не хранится, используем приближение
        
        sessions.append({
            'ID': session_id[:8],  # Сокращаем для удобства
            'Последний доступ': datetime.fromtimestamp(last_access_time).strftime('%Y-%m-%d %H:%M:%S'),
            'Возраст (час)': f"{(time.time() - last_access_time) / 3600:.1f}",
            'Данные': len(session_data),
            'Полный ID': session_id
        })
    
    # Также проверяем файлы сессий на диске, которые могут еще не быть загружены в память
    for filename in os.listdir(session_dir):
        if filename.startswith("session_") and filename.endswith(".pkl"):
            file_path = os.path.join(session_dir, filename)
            
            # Получаем время последней модификации файла
            mtime = os.path.getmtime(file_path)
            file_size = os.path.getsize(file_path)
            
            # Извлекаем ID сессии из имени файла (убираем префикс и расширение)
            # Так как мы используем хеширование для имен файлов, это приближение
            file_id = filename[8:-4]  # Убираем 'session_' и '.pkl'
            
            # Добавляем сессию, только если она еще не была добавлена из _sessions
            if not any(s['Полный ID'] == file_id for s in sessions):
                sessions.append({
                    'ID': file_id[:8],
                    'Последний доступ': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'Возраст (час)': f"{(time.time() - mtime) / 3600:.1f}",
                    'Данные': file_size,
                    'Полный ID': file_id
                })
    
    if sessions:
        sessions_df = pd.DataFrame(sessions)
        st.dataframe(sessions_df.drop(columns=['Полный ID']))  # Не показываем полный ID в таблице
        
        # Добавляем кнопки для управления сессиями
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Очистить все сессии"):
                # Удаляем все файлы сессий
                for filename in os.listdir(session_dir):
                    if filename.startswith("session_") and filename.endswith(".pkl"):
                        try:
                            os.remove(os.path.join(session_dir, filename))
                        except Exception as e:
                            st.error(f"Ошибка при удалении файла {filename}: {e}")
                
                # Очищаем словари в памяти
                session_manager._sessions.clear()
                session_manager._session_last_access.clear()
                
                st.success("Все сессии удалены")
                st.experimental_rerun()
        
        with col2:
            if st.button("Удалить старые сессии"):
                removed = session_manager.cleanup_old_sessions()
                st.success(f"Удалено {removed} старых сессий")
                st.experimental_rerun()
    else:
        st.info("Активных сессий не найдено")

def show_logs_management():
    """Раздел управления логами"""
    st.header("Системные логи")
    
    # Читаем логи
    logs = read_logs(max_lines=1000)
    
    # Фильтрация логов
    st.subheader("Фильтры")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        log_level_filter = st.selectbox(
            "Уровень логов", 
            ["ВСЕ", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        )
    
    with col2:
        log_module_filter = st.text_input("Модуль", "")
    
    with col3:
        log_message_filter = st.text_input("Сообщение содержит", "")
    
    # Применяем фильтры
    filtered_logs = logs
    if log_level_filter != "ВСЕ":
        filtered_logs = [log for log in filtered_logs if f"[{log_level_filter}]" in log]
    
    if log_module_filter:
        filtered_logs = [log for log in filtered_logs if log_module_filter in log]
    
    if log_message_filter:
        filtered_logs = [log for log in filtered_logs if log_message_filter.lower() in log.lower()]
    
    # Отображаем отфильтрованные логи
    st.subheader("Логи")
    
    # Убираем использование st.code и заменяем на текстовую область с фиксированной шириной
    st.markdown("""
    <style>
    .log-container {
        font-family: monospace;
        white-space: pre;
        overflow-x: auto;
        border: 1px solid #e0e0e0;
        padding: 10px;
        background-color: #f9f9f9;
        max-height: 500px;
        overflow-y: auto;
    }
    </style>
    """, unsafe_allow_html=True)
    
    log_text = "\n".join(filtered_logs)
    st.markdown(f'<div class="log-container">{log_text}</div>', unsafe_allow_html=True)
    
    # Действия с логами
    st.subheader("Действия")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Очистить логи", key="clear_logs"):
            clear_logs()
            st.success("Логи очищены!")
    
    with col2:
        if st.button("Обновить", key="refresh_logs"):
            st.rerun() 