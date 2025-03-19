# src/config.py
"""
Legacy configuration module - this will redirect to the centralized configuration.
This is maintained for backward compatibility, but all new code should use src.utils.config directly.
"""
import warnings
from pathlib import Path

# Import only what we need from the central config
from src.utils.config import (
    APP_ROOT, TIMESERIES_MODELS_DIR, MODEL_METADATA_FILE, LOGS_DIR, CONFIG_DIR,
    DEFAULT_CHUNK_SIZE, DEFAULT_PREDICTION_LENGTH, DEFAULT_TIME_LIMIT,
    MAX_VISUALIZE_POINTS, MAX_MEMORY_USAGE_GB
)

# Show deprecation warning when this module is imported
warnings.warn(
    "The src.config module is deprecated. Please use src.utils.config instead.",
    DeprecationWarning,
    stacklevel=2
)

def get_config(key, default=None):
    """
    Legacy function that gets a configuration value from the centralized config.
    For backward compatibility only.
    
    Args:
        key (str): Configuration key
        default (any, optional): Default value if key not found
        
    Returns:
        any: Configuration value or default
    """
    # Map old config keys to new ones
    key_mapping = {
        "MODEL_DIR": str(TIMESERIES_MODELS_DIR),
        "MODEL_INFO_FILE": str(MODEL_METADATA_FILE),
        "LOG_FILE": str(LOGS_DIR / "app.log"),
        "CONFIG_PATH": str(CONFIG_DIR / "config.yaml"),
        "DEFAULT_CHUNK_SIZE": DEFAULT_CHUNK_SIZE,
        "DEFAULT_PREDICTION_LENGTH": DEFAULT_PREDICTION_LENGTH,
        "DEFAULT_TIME_LIMIT": DEFAULT_TIME_LIMIT,
        "DEFAULT_FREQ": "auto (угадать)",
        "DEFAULT_FILL_METHOD": "None",
        "DEFAULT_METRIC": "MASE (Mean absolute scaled error)",
        "DEFAULT_PRESET": "medium_quality",
        "MAX_VISIBLE_ROWS": 1000,
        "MAX_PLOT_POINTS": MAX_VISUALIZE_POINTS,
        "MAX_IDS_FOR_PLOT": 10,
        "MEMORY_THRESHOLD_GB": MAX_MEMORY_USAGE_GB,
        "ENABLE_CHUNK_PROCESSING": True
    }
    
    if key in key_mapping:
        return key_mapping[key]
    
    # Try to find in the global variables of the config module
    import src.utils.config as config_module
    if hasattr(config_module, key):
        return getattr(config_module, key)
    
    return default

def get_full_path(relative_path):
    """
    Legacy function that gets a full path relative to the project root.
    For backward compatibility only.
    
    Args:
        relative_path (str): Relative path
        
    Returns:
        str: Full path
    """
    return str(APP_ROOT / relative_path)