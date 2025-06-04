from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import logging
from datetime import datetime
import tempfile
import shutil

router = APIRouter()
logger = logging.getLogger(__name__)

# Путь к файлу логов
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")

@router.get("/logs/download")
async def download_logs():
    """
    Скачать файл логов
    """
    try:
        if not os.path.exists(LOG_FILE_PATH):
            logger.warning(f"Log file not found: {LOG_FILE_PATH}")
            raise HTTPException(status_code=404, detail="Файл логов не найден")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"app_logs_{timestamp}.log"

        # Копируем лог во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
            shutil.copyfile(LOG_FILE_PATH, tmp.name)
            tmp_path = tmp.name

        logger.info(f"Downloading logs file: {filename}")
        
        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="text/plain"
        )
    
    except HTTPException:
        # Пробрасываем HTTPException дальше
        raise
    except Exception as e:
        logger.error(f"Error downloading logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при скачивании логов: {str(e)}")

@router.post("/logs/clear")
async def clear_logs():
    """
    Очистить файл логов (сделать его пустым)
    """
    try:
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        
        # Очищаем файл (делаем его пустым) или создаем новый пустой
        with open(LOG_FILE_PATH, 'w', encoding='utf-8') as f:
            pass
        
        logger.info("Log file cleared successfully")
        
        return {
            "success": True,
            "message": "Логи успешно очищены"
        }
    
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке логов: {str(e)}")

@router.get("/logs/info")
async def get_logs_info():
    """
    Получить информацию о файле логов
    """
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return {
                "exists": False,
                "size": 0,
                "message": "Файл логов не существует"
            }
        
        file_size = os.path.getsize(LOG_FILE_PATH)
        file_modified = datetime.fromtimestamp(os.path.getmtime(LOG_FILE_PATH))
        
        return {
            "exists": True,
            "size": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "last_modified": file_modified.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Информация о файле логов"
        }
    
    except Exception as e:
        logger.error(f"Error getting logs info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении информации о логах: {str(e)}")
