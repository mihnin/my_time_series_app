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

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import try_load_existing_model, save_model_metadata, load_model_metadata
from src.utils.utils import setup_logger, read_logs, LOG_FILE
from src.help_page import show_help_page
from src.utils.exporter import generate_excel_buffer
from data_analysis import run_data_analysis

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
            
    except Exception as e:
        logging.error(f"Ошибка при выполнении функции main: {e}")
        st.error(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    main()

