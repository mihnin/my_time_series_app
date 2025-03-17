# app.py
import streamlit as st
import logging
import os
import zipfile
import io
import pandas as pd
import psutil
from openpyxl.styles import PatternFill
import time
import threading
import shutil
import datetime
from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import try_load_existing_model, save_model_metadata, load_model_metadata
from src.utils.utils import setup_logger, read_logs, LOG_FILE, LOGS_DIR
from src.help_page import show_help_page
from src.utils.exporter import generate_excel_buffer
from data_analysis import run_data_analysis

# Функция для удаления логов
def clear_logs():
    """Очищает текущие логи и архивирует старые"""
    try:
        # Проверяем существование директории для архивов
        archive_dir = os.path.join(LOGS_DIR, "archive")
        os.makedirs(archive_dir, exist_ok=True)
        
        # Если существует файл логов
        if os.path.exists(LOG_FILE):
            # Сначала архивируем текущий лог
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"app_log_{timestamp}.log"
            archive_path = os.path.join(archive_dir, archive_filename)
            
            # Копируем текущий лог в архив
            shutil.copy2(LOG_FILE, archive_path)
            
            # Теперь очищаем текущий лог
            with open(LOG_FILE, 'w') as f:
                f.write(f"# Логи очищены {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
            return True, f"Логи успешно очищены. Предыдущая версия сохранена как {archive_filename}"
        else:
            return False, "Файл логов не найден"
    except Exception as e:
        logging.error(f"Ошибка при очистке логов: {str(e)}")
        return False, f"Ошибка при очистке логов: {str(e)}"

# Функция для отображения системных ресурсов
def show_system_resources():
    """Показывает статус использования системных ресурсов"""
    st.subheader("💻 Системные ресурсы")
    
    # Получаем данные о ресурсах
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Создаем три колонки для CPU, Памяти и Диска
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Определяем цвет для CPU
        cpu_color = "#4CAF50" if cpu_percent < 80 else "#E53935"
        st.markdown(f"#### CPU <span style='color:{cpu_color}'>{cpu_percent:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Прогресс бар для CPU
        st.progress(cpu_percent/100, text=f"{cpu_percent:.1f}%")
        
        # Информация о процессоре
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        st.caption(f"Ядра: {cpu_count} физ. / {cpu_logical} лог.")
    
    with col2:
        # Определяем цвет для памяти
        memory_color = "#4CAF50" if memory.percent < 80 else "#E53935"
        st.markdown(f"#### Память <span style='color:{memory_color}'>{memory.percent:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Прогресс бар для памяти
        st.progress(memory.percent/100, text=f"{memory.percent:.1f}%")
        
        # Информация о памяти
        total_gb = memory.total / (1024**3)
        used_gb = memory.used / (1024**3)
        st.caption(f"Использовано: {used_gb:.1f} ГБ из {total_gb:.1f} ГБ")
    
    with col3:
        # Определяем цвет для диска
        disk_color = "#4CAF50" if disk.percent < 90 else "#E53935"
        st.markdown(f"#### Диск <span style='color:{disk_color}'>{disk.percent:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Прогресс бар для диска
        st.progress(disk.percent/100, text=f"{disk.percent:.1f}%")
        
        # Информация о диске
        total_gb = disk.total / (1024**3)
        free_gb = disk.free / (1024**3)
        st.caption(f"Свободно: {free_gb:.1f} ГБ из {total_gb:.1f} ГБ")

def main():
    """Основная функция приложения"""
    try:
        # Настраиваем логгер
        setup_logger()
        logging.info("========== Приложение запущено ========== ")
        
        # Настройка Streamlit для полноэкранного режима
        st.set_page_config(
            page_title="Прогнозирование временных рядов", 
            page_icon="📈", 
            layout="wide",  # Широкий макет
            initial_sidebar_state="expanded"  # Расширенный сайдбар
        )
        
        # Настраиваем интерфейс
        page_choice = setup_ui()
        
        # Показываем системные ресурсы в правой колонке
        if page_choice == "Главная":
            # Показываем состояние системы
            st.sidebar.markdown("---")
            show_system_resources()
                
        # В зависимости от выбранной страницы показываем соответствующий контент
        if page_choice == "Анализ данных":
            run_data_analysis()
        elif page_choice == "Help":
            show_help_page()
            
        # Обработка действий и кнопок
        if st.sidebar.button("🚀 Обучить модель", key="sidebar_fit_model_btn", use_container_width=True):
            run_training()
        
        # === ОБРАБОТЧИКИ КНОПОК СОХРАНЕНИЯ И ЛОГОВ ===
        
        # Проверяем, есть ли прогнозы для сохранения
        forecasts_available = 'forecasts' in st.session_state and st.session_state['forecasts'] is not None
        
        # Сохранение результатов в Excel
        if st.session_state.get('excel_save_clicked', False):
            # После обработки сбрасываем флаг
            st.session_state['excel_save_clicked'] = False
            
            if forecasts_available:
                try:
                    # Используем функцию для создания Excel
                    excel_buffer = generate_excel_buffer(
                        st.session_state.get('forecasts'),
                        st.session_state.get('leaderboard'),
                        None,  # статический датафрейм
                        None   # информация о моделях ансамбля
                    )
                    
                    # Кнопка для скачивания Excel
                    st.sidebar.download_button(
                        label="📥 Скачать Excel",
                        data=excel_buffer.getvalue(),
                        file_name="forecast_results.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    st.sidebar.success("Excel готов для скачивания!")
                except Exception as e:
                    st.sidebar.error(f"Ошибка при создании Excel: {str(e)}")
                    logging.error(f"Ошибка при создании Excel: {str(e)}")
                    
            else:
                st.sidebar.warning("Нет данных прогноза для сохранения в Excel")
        
        # Показать логи
        if st.session_state.get('logs_show_clicked', False):
            # После обработки сбрасываем флаг
            st.session_state['logs_show_clicked'] = False
            
            try:
                logs = read_logs()
                if logs:
                    st.sidebar.text_area("Логи приложения", logs, height=300)
                else:
                    st.sidebar.info("Логи пусты или файл логов не найден")
            except Exception as e:
                st.sidebar.error(f"Ошибка при чтении логов: {str(e)}")
                logging.error(f"Ошибка при чтении логов: {str(e)}")
        
        # Скачать логи
        if st.session_state.get('logs_download_clicked', False):
            # После обработки сбрасываем флаг
            st.session_state['logs_download_clicked'] = False
            
            try:
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r", encoding="utf-8") as log_file:
                        logs_content = log_file.read()
                    
                    st.sidebar.download_button(
                        label="📥 Скачать файл логов",
                        data=logs_content,
                        file_name="app_logs.log",
                        mime="text/plain",
                    )
                    st.sidebar.success("Файл логов готов для скачивания!")
                else:
                    st.sidebar.warning("Файл логов не найден")
            except Exception as e:
                st.sidebar.error(f"Ошибка при подготовке логов: {str(e)}")
                logging.error(f"Ошибка при подготовке логов: {str(e)}")
        
        # Очистить логи
        if st.session_state.get('logs_clear_clicked', False):
            # После обработки сбрасываем флаг
            st.session_state['logs_clear_clicked'] = False
            
            success, message = clear_logs()
            if success:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)
        
        # Скачать архив с моделями и логами
        if st.session_state.get('model_download_clicked', False):
            # После обработки сбрасываем флаг
            st.session_state['model_download_clicked'] = False
            
            try:
                # Создаем буфер для архива
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Добавляем логи в архив
                    if os.path.exists(LOG_FILE):
                        zip_file.write(LOG_FILE, arcname="logs/app_logs.log")
                    
                    # Добавляем архивные логи если они есть
                    archive_dir = os.path.join(LOGS_DIR, "archive")
                    if os.path.exists(archive_dir):
                        for root, dirs, files in os.walk(archive_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                archive_path = os.path.join("logs/archive", file)
                                zip_file.write(file_path, arcname=archive_path)
                    
                    # Добавляем файлы модели в архив
                    model_directory = "AutogluonModels/TimeSeriesModel"
                    if os.path.exists(model_directory):
                        for root, dirs, files in os.walk(model_directory):
                            for file in files:
                                file_path = os.path.join(root, file)
                                archive_path = os.path.join("models", os.path.relpath(file_path, model_directory))
                                zip_file.write(file_path, arcname=archive_path)
                
                # Создаем кнопку для скачивания архива
                st.sidebar.download_button(
                    label="📥 Скачать архив",
                    data=zip_buffer.getvalue(),
                    file_name="model_and_logs.zip",
                    mime="application/zip",
                )
                st.sidebar.success("Архив с моделями и логами готов для скачивания!")
            except Exception as e:
                st.sidebar.error(f"Ошибка при создании архива: {str(e)}")
                logging.error(f"Ошибка при создании архива: {str(e)}")
            
    except Exception as e:
        st.error(f"Ошибка в приложении: {str(e)}")
        logging.exception("Необработанная ошибка в приложении:")

if __name__ == "__main__":
    main()

