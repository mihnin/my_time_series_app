# src/components/queue_status.py
import streamlit as st
import time
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.utils.queue_manager import get_queue_manager, Task, TaskStatus, TaskPriority
from src.utils.resource_monitor import get_resource_monitor, get_system_status_info
from src.utils.session_manager import get_current_session_id

def format_time_ago(timestamp: float) -> str:
    """Форматирует время в человекочитаемую строку (например, '2 мин назад')"""
    if not timestamp:
        return "н/д"
    
    seconds_ago = int(time.time() - timestamp)
    
    if seconds_ago < 0:
        return "в будущем"
    elif seconds_ago < 10:
        return "только что"
    elif seconds_ago < 60:
        return f"{seconds_ago} сек назад"
    elif seconds_ago < 3600:
        minutes = seconds_ago // 60
        return f"{minutes} мин назад"
    elif seconds_ago < 86400:
        hours = seconds_ago // 3600
        return f"{hours} ч назад"
    else:
        days = seconds_ago // 86400
        return f"{days} д назад"

def format_duration(seconds: float) -> str:
    """Форматирует длительность в человекочитаемую строку"""
    if seconds < 0:
        return "н/д"
    elif seconds < 1:
        return f"{int(seconds * 1000)} мс"
    elif seconds < 60:
        return f"{seconds:.1f} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds_remainder = seconds % 60
        return f"{int(minutes)}м {int(seconds_remainder)}с"
    else:
        hours = seconds // 3600
        minutes_remainder = (seconds % 3600) // 60
        return f"{int(hours)}ч {int(minutes_remainder)}м"

def get_task_duration(task: Task) -> float:
    """Возвращает продолжительность выполнения задачи в секундах"""
    if not task.started_at:
        return 0
    
    end_time = task.completed_at if task.completed_at else time.time()
    return end_time - task.started_at

def get_task_wait_time(task: Task) -> float:
    """Возвращает время ожидания задачи в очереди"""
    if not task.started_at:
        # Задача еще в очереди
        return time.time() - task.created_at
    else:
        # Задача уже начала выполняться
        return task.started_at - task.created_at

def get_status_color(status: TaskStatus) -> str:
    """Возвращает цвет для статуса задачи"""
    status_colors = {
        TaskStatus.QUEUED: "#FFA726",     # Оранжевый
        TaskStatus.PROCESSING: "#1E88E5",  # Синий
        TaskStatus.COMPLETED: "#4CAF50",   # Зеленый
        TaskStatus.FAILED: "#E53935",      # Красный
        TaskStatus.CANCELLED: "#90A4AE"    # Серый
    }
    return status_colors.get(status, "#607D8B")  # По умолчанию темно-серый

def get_priority_label(priority: TaskPriority) -> str:
    """Возвращает метку для приоритета задачи"""
    priority_labels = {
        TaskPriority.LOW: "Низкий",
        TaskPriority.NORMAL: "Обычный",
        TaskPriority.HIGH: "Высокий"
    }
    return priority_labels.get(priority, "Неизвестно")

def show_queue_status(key_suffix=""):
    """
    Отображает статус очереди задач для текущей сессии
    
    Parameters:
    -----------
    key_suffix : str, optional
        Суффикс для создания уникальных ключей виджетов (по умолчанию "")
    """
    # Получаем текущий ID сессии
    session_id = get_current_session_id()
    
    # Получаем менеджер очереди
    queue_manager = get_queue_manager()
    
    # Получаем все задачи для текущей сессии
    session_tasks = queue_manager.get_session_tasks(session_id)
    
    # Кнопка обновления
    col1, col2 = st.columns([9, 1])
    with col1:
        st.markdown("**Ваши задачи**")
    with col2:
        # Используем уникальный ключ, добавляя к нему суффикс
        refresh_key = f"refresh_queue{key_suffix}"
        st.button("🔄", key=refresh_key, help="Обновить статус очереди")
    
    # Если нет задач, показываем сообщение
    if not session_tasks:
        st.info("У вас пока нет задач в очереди.")
        return
    
    # Сортируем задачи: сначала выполняющиеся, затем в очереди, затем завершенные
    session_tasks.sort(key=lambda t: (
        t.status != TaskStatus.PROCESSING,  # Сначала выполняющиеся
        t.status != TaskStatus.QUEUED,      # Затем в очереди
        t.created_at                        # Затем по времени создания
    ))
    
    # Разделяем задачи по статусам для разных секций
    active_tasks = [t for t in session_tasks if t.status in (TaskStatus.PROCESSING, TaskStatus.QUEUED)]
    completed_tasks = [t for t in session_tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)]
    
    # Показываем активные задачи
    if active_tasks:
        for task in active_tasks:
            with st.container():
                # Создаем карточку для задачи
                with st.expander(f"{'🔄' if task.status == TaskStatus.PROCESSING else '⏳'} Задача {task.id[:8]}", expanded=True):
                    # Верхняя строка с статусом и временем
                    status_text = "Выполняется" if task.status == TaskStatus.PROCESSING else "В очереди"
                    
                    cols = st.columns([3, 2, 2])
                    with cols[0]:
                        st.markdown(f"**Статус:** <span style='color:{get_status_color(task.status)}'>{status_text}</span>", unsafe_allow_html=True)
                    with cols[1]:
                        if task.status == TaskStatus.PROCESSING:
                            duration = get_task_duration(task)
                            st.markdown(f"**Выполняется:** {format_duration(duration)}")
                        else:
                            wait_time = get_task_wait_time(task)
                            st.markdown(f"**В очереди:** {format_duration(wait_time)}")
                    with cols[2]:
                        st.markdown(f"**Приоритет:** {get_priority_label(task.priority)}")
                    
                    # Прогресс выполнения
                    st.progress(task.progress, text=f"{int(task.progress * 100)}%")
                    
                    # Время создания
                    st.markdown(f"**Создана:** {format_time_ago(task.created_at)}")
                    
                    # Кнопка отмены для задач в очереди
                    if task.status == TaskStatus.QUEUED:
                        if st.button("Отменить", key=f"cancel_{task.id}", help="Отменить выполнение задачи"):
                            if queue_manager.cancel_task(task.id):
                                st.success("Задача отменена")
                                st.rerun()
                            else:
                                st.error("Не удалось отменить задачу")
    
    # Показываем завершенные задачи в отдельном блоке
    if completed_tasks:
        with st.expander("Завершенные задачи", expanded=False):
            for task in completed_tasks:
                status_map = {
                    TaskStatus.COMPLETED: "✅ Выполнена",
                    TaskStatus.FAILED: "❌ Ошибка",
                    TaskStatus.CANCELLED: "🚫 Отменена"
                }
                status_text = status_map.get(task.status, "Неизвестно")
                
                # Компактный вид для каждой задачи
                cols = st.columns([5, 3, 2])
                with cols[0]:
                    st.markdown(f"**{status_text}** - ID: {task.id[:8]}")
                with cols[1]:
                    if task.completed_at:
                        st.markdown(f"**Завершена:** {format_time_ago(task.completed_at)}")
                with cols[2]:
                    if task.started_at and task.completed_at:
                        duration = task.completed_at - task.started_at
                        st.markdown(f"**Длительность:** {format_duration(duration)}")
                
                # Если задача завершилась с ошибкой, показываем ошибку
                if task.status == TaskStatus.FAILED and task.error:
                    st.error(f"Ошибка: {task.error}")

def show_system_status():
    """Отображает статус системных ресурсов"""
    status_info = get_system_status_info()
    
    st.markdown("### Состояние системы")
    
    # Общий статус системы
    status_color = "#4CAF50" if status_info['system_ok'] else "#E53935"
    status_text = "Нормальное" if status_info['system_ok'] else "Перегружена"
    
    st.markdown(f"**Состояние:** <span style='color:{status_color}'>{status_text}</span>", 
                unsafe_allow_html=True)
    
    # Создаем три колонки для CPU, Памяти и Диска
    col1, col2, col3 = st.columns(3)
    
    with col1:
        cpu_color = "#4CAF50" if not status_info['cpu']['overloaded'] else "#E53935"
        st.markdown(f"#### CPU <span style='color:{cpu_color}'>{status_info['cpu']['percent']:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Создаем круговую диаграмму для CPU
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=status_info['cpu']['percent'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': cpu_color},
                'steps': [
                    {'range': [0, status_info['cpu']['threshold']], 'color': "#DDDDEE"},
                    {'range': [status_info['cpu']['threshold'], 100], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 2},
                    'thickness': 0.75,
                    'value': status_info['cpu']['threshold']
                }
            },
            number={'suffix': "%"}
        ))
        
        fig.update_layout(
            height=200, 
            margin=dict(l=10, r=10, t=30, b=10),
            font={'size': 14}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Ядра: {status_info['cpu']['physical_count']} физ. / {status_info['cpu']['count']} лог.")
    
    with col2:
        memory_color = "#4CAF50" if not status_info['memory']['overloaded'] else "#E53935"
        st.markdown(f"#### Память <span style='color:{memory_color}'>{status_info['memory']['percent']:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Создаем круговую диаграмму для Памяти
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=status_info['memory']['percent'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': memory_color},
                'steps': [
                    {'range': [0, status_info['memory']['threshold']], 'color': "#DDDDEE"},
                    {'range': [status_info['memory']['threshold'], 100], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 2},
                    'thickness': 0.75,
                    'value': status_info['memory']['threshold']
                }
            },
            number={'suffix': "%"}
        ))
        
        fig.update_layout(
            height=200, 
            margin=dict(l=10, r=10, t=30, b=10),
            font={'size': 14}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Всего: {status_info['memory']['total_gb']:.1f} ГБ | Доступно: {status_info['memory']['available_gb']:.1f} ГБ")
    
    with col3:
        disk_color = "#4CAF50" if not status_info['disk']['overloaded'] else "#E53935"
        st.markdown(f"#### Диск <span style='color:{disk_color}'>{status_info['disk']['percent']:.1f}%</span>", 
                    unsafe_allow_html=True)
        
        # Создаем круговую диаграмму для Диска
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=status_info['disk']['percent'],
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': disk_color},
                'steps': [
                    {'range': [0, status_info['disk']['threshold']], 'color': "#DDDDEE"},
                    {'range': [status_info['disk']['threshold'], 100], 'color': "#FFCCCC"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 2},
                    'thickness': 0.75,
                    'value': status_info['disk']['threshold']
                }
            },
            number={'suffix': "%"}
        ))
        
        fig.update_layout(
            height=200, 
            margin=dict(l=10, r=10, t=30, b=10),
            font={'size': 14}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Всего: {status_info['disk']['total_gb']:.1f} ГБ | Свободно: {status_info['disk']['free_gb']:.1f} ГБ") 