# src/utils/queue_manager.py
import time
import uuid
import threading
import logging
import queue
from typing import Dict, List, Any, Callable, Optional
from enum import Enum, auto
from dataclasses import dataclass, field

class TaskStatus(Enum):
    """Статусы задачи в очереди"""
    QUEUED = auto()     # В очереди
    PROCESSING = auto() # Выполняется
    COMPLETED = auto()  # Завершено успешно
    FAILED = auto()     # Завершено с ошибкой
    CANCELLED = auto()  # Отменено

class TaskPriority(Enum):
    """Приоритеты задач"""
    LOW = 0     # Низкий приоритет
    NORMAL = 1  # Обычный приоритет 
    HIGH = 2    # Высокий приоритет

@dataclass
class Task:
    """Класс задачи для очереди обработки"""
    id: str                       # Уникальный идентификатор
    session_id: str               # Идентификатор сессии пользователя
    func: Callable                # Функция для выполнения
    args: tuple = field(default_factory=tuple)   # Позиционные аргументы
    kwargs: dict = field(default_factory=dict)   # Именованные аргументы
    priority: TaskPriority = TaskPriority.NORMAL # Приоритет задачи
    status: TaskStatus = TaskStatus.QUEUED       # Статус задачи
    result: Any = None                           # Результат выполнения
    error: Optional[Exception] = None            # Ошибка (если есть)
    created_at: float = field(default_factory=time.time)  # Время создания
    started_at: Optional[float] = None           # Время начала выполнения
    completed_at: Optional[float] = None         # Время завершения
    progress: float = 0.0                        # Прогресс выполнения (0-1)
    
    def __lt__(self, other):
        # Для сравнения в приоритетной очереди
        return self.priority.value > other.priority.value
    
    def to_dict(self):
        """Преобразует задачу в словарь для сериализации"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'status': self.status.name,
            'priority': self.priority.name,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'progress': self.progress,
            'error': str(self.error) if self.error else None
        }

class QueueManager:
    """Менеджер очереди задач"""
    _instance = None
    
    def __new__(cls):
        # Синглтон для доступа к одному экземпляру из разных частей приложения
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Инициализация при первом создании
        self.task_queue = queue.PriorityQueue()
        self.tasks: Dict[str, Task] = {}  # id -> Task
        self.session_tasks: Dict[str, List[str]] = {}  # session_id -> [task_ids]
        self.lock = threading.RLock()  # Для потокобезопасного доступа
        self.workers = []  # Список рабочих потоков
        self.max_workers = 2  # Максимальное количество одновременных задач
        self.running = True  # Флаг для остановки воркеров
        self._start_workers()
        self._initialized = True
        logging.info("Менеджер очереди задач инициализирован")
    
    def _start_workers(self) -> None:
        """Запускает рабочие потоки для обработки очереди"""
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"QueueWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)
            logging.info(f"Запущен рабочий поток {worker.name}")
    
    def _worker_loop(self) -> None:
        """Основной цикл рабочего потока"""
        while self.running:
            try:
                # Получаем задачу с таймаутом, чтобы можно было остановить поток
                _, task_id = self.task_queue.get(timeout=1.0)
                
                with self.lock:
                    if task_id not in self.tasks:
                        self.task_queue.task_done()
                        continue
                    
                    task = self.tasks[task_id]
                    task.status = TaskStatus.PROCESSING
                    task.started_at = time.time()
                
                logging.info(f"Начало выполнения задачи {task_id}")
                
                try:
                    # Выполняем задачу
                    result = task.func(*task.args, **task.kwargs)
                    
                    with self.lock:
                        task.result = result
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = time.time()
                        task.progress = 1.0
                    
                    logging.info(f"Задача {task_id} успешно выполнена")
                
                except Exception as e:
                    logging.exception(f"Ошибка при выполнении задачи {task_id}: {e}")
                    
                    with self.lock:
                        task.error = e
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                
                finally:
                    self.task_queue.task_done()
            
            except queue.Empty:
                # Нет задач, просто продолжаем цикл
                pass
            except Exception as e:
                logging.exception(f"Ошибка в цикле обработки задач: {e}")
    
    def add_task(self, session_id: str, func: Callable, *args, 
                priority: TaskPriority = TaskPriority.NORMAL, **kwargs) -> str:
        """Добавляет новую задачу в очередь и возвращает её ID"""
        task_id = str(uuid.uuid4())
        
        task = Task(
            id=task_id,
            session_id=session_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority
        )
        
        with self.lock:
            self.tasks[task_id] = task
            
            if session_id not in self.session_tasks:
                self.session_tasks[session_id] = []
            
            self.session_tasks[session_id].append(task_id)
            # Добавляем в приоритетную очередь (меньшее число = выше приоритет)
            self.task_queue.put((priority.value, task_id))
        
        logging.info(f"Задача {task_id} добавлена в очередь. Приоритет: {priority.name}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Возвращает задачу по ID"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_session_tasks(self, session_id: str) -> List[Task]:
        """Возвращает все задачи для сессии"""
        with self.lock:
            task_ids = self.session_tasks.get(session_id, [])
            return [self.tasks[task_id] for task_id in task_ids if task_id in self.tasks]
    
    def cancel_task(self, task_id: str) -> bool:
        """Отменяет задачу, если она еще не выполняется"""
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            
            if task.status == TaskStatus.QUEUED:
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
                logging.info(f"Задача {task_id} отменена")
                return True
                
            # Задачу уже выполняется или завершена - нельзя отменить
            return False
    
    def clean_completed_tasks(self, max_age_seconds: int = 3600) -> int:
        """Удаляет завершенные задачи старше указанного возраста"""
        now = time.time()
        count = 0
        
        with self.lock:
            for task_id in list(self.tasks.keys()):
                task = self.tasks[task_id]
                
                if (task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) and
                    task.completed_at and (now - task.completed_at) > max_age_seconds):
                    
                    # Удаляем задачу
                    del self.tasks[task_id]
                    
                    # Удаляем из списка сессии
                    if task.session_id in self.session_tasks:
                        if task_id in self.session_tasks[task.session_id]:
                            self.session_tasks[task.session_id].remove(task_id)
                        
                        # Если у сессии не осталось задач, удаляем и её
                        if not self.session_tasks[task.session_id]:
                            del self.session_tasks[task.session_id]
                    
                    count += 1
        
        if count > 0:
            logging.info(f"Удалено {count} старых завершенных задач")
        
        return count

    def update_task_progress(self, task_id: str, progress: float) -> bool:
        """Обновляет прогресс выполнения задачи"""
        with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            
            if task.status != TaskStatus.PROCESSING:
                return False
            
            task.progress = max(0.0, min(1.0, progress))  # Ограничиваем 0-1
            return True
    
    def shutdown(self) -> None:
        """Останавливает все рабочие потоки и очищает ресурсы"""
        logging.info("Остановка менеджера очереди задач...")
        self.running = False
        
        # Ждем завершения всех рабочих потоков
        for worker in self.workers:
            worker.join(timeout=2.0)
        
        logging.info("Менеджер очереди задач остановлен")


# Функция для получения экземпляра менеджера очереди
def get_queue_manager() -> QueueManager:
    """Возвращает экземпляр менеджера очереди (синглтон)"""
    return QueueManager() 