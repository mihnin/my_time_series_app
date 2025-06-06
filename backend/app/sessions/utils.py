import os
import json
import shutil
from typing import Dict, Any
from datetime import datetime

import pandas as pd

# Base path for all training sessions - now relative to backend/app directory
SESSIONS_BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "training_sessions")

def get_session_path(session_id: str) -> str:
    """Get the full path to a session directory."""
    return os.path.join(SESSIONS_BASE_PATH, session_id)

def create_session_directory(session_id: str) -> str:
    """Create a new session directory and return its path."""
    session_path = get_session_path(session_id)
    os.makedirs(session_path, exist_ok=True)
    return session_path

def save_session_metadata(session_id: str, metadata: Dict[str, Any]) -> None:
    """Save session metadata to the session directory."""
    session_path = get_session_path(session_id)
    metadata_path = os.path.join(session_path, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

def load_session_metadata(session_id: str) -> Dict[str, Any]:
    """Load session metadata from the session directory."""
    session_path = get_session_path(session_id)
    metadata_path = os.path.join(session_path, "metadata.json")
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def cleanup_old_sessions(max_age_days: int = 7) -> None:
    """Remove session directories older than max_age_days."""
    if not os.path.exists(SESSIONS_BASE_PATH):
        return

    now = datetime.now()
    for session_id in os.listdir(SESSIONS_BASE_PATH):
        session_path = get_session_path(session_id)
        try:
            metadata = load_session_metadata(session_id)
            create_time = datetime.fromisoformat(metadata.get("create_time", ""))
            age_days = (now - create_time).days
            
            if age_days > max_age_days:
                shutil.rmtree(session_path)
        except (ValueError, FileNotFoundError):
            # If we can't determine the age, leave it for manual cleanup
            pass

def save_training_file(session_id: str, file_content: bytes, original_filename: str) -> str:
    """Save a training file to the session directory and return its path."""
    session_path = get_session_path(session_id)
    file_ext = os.path.splitext(original_filename)[1]
    training_file_path = os.path.join(session_path, f"training_data{file_ext}")
    
    with open(training_file_path, "wb") as f:
        f.write(file_content)
    
    return training_file_path

def get_model_path(session_id: str) -> str:
    """Get the path for storing model files in the session directory."""
    return os.path.join(get_session_path(session_id), "model")

# Глобальный словарь для хранения статусов сессий обучения
training_sessions = {}