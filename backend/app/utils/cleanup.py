import os
import shutil
import time
import re
import tempfile
from datetime import datetime, timedelta
import logging

def cleanup_old_training_sessions(training_sessions_dir: str):
    now = time.time()
    for folder in os.listdir(training_sessions_dir):
        folder_path = os.path.join(training_sessions_dir, folder)
        if os.path.isdir(folder_path):
            mtime = os.path.getmtime(folder_path)
            # 2 days = 172800 seconds
            if now - mtime > 2 * 24 * 60 * 60:
                try:
                    shutil.rmtree(folder_path)
                    logging.info(f"Deleted old training session folder: {folder_path}")
                except Exception as e:
                    logging.error(f"Failed to delete {folder_path}: {e}")
