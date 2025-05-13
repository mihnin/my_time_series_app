from fastapi import APIRouter, FastAPI, File, UploadFile, HTTPException, Depends, Form, BackgroundTasks
import pandas as pd
import numpy as np
import shutil
import logging
import time
import gc
import os
import psutil
import json
import tempfile
import uuid
import asyncio
from functools import partial
from typing import Dict, Optional
from datetime import datetime

from autogluon.timeseries import TimeSeriesPredictor
from .model import TrainingParameters
from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries, safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from src.validation.data_validation import validate_dataset
from .utils import (
    create_session_directory,
    save_session_metadata,
    load_session_metadata,
    cleanup_old_sessions,
    save_training_file,
    get_model_path,
)

# Global training status tracking
training_sessions: Dict[str, Dict] = {}

# Run cleanup of old sessions at startup
cleanup_old_sessions()

router = APIRouter()

def get_training_status(session_id: str) -> Optional[Dict]:
    """Get the current status of a training session."""
    if session_id not in training_sessions:
        # Try to load from file
        try:
            metadata = load_session_metadata(session_id)
            if metadata:
                training_sessions[session_id] = metadata
        except:
            return None
    return training_sessions.get(session_id)

async def run_training_async(
    session_id: str,
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    original_filename: str
):
    """Run the training process in a separate thread."""
    try:
        # Create session directory and save initial status
        session_path = create_session_directory(session_id)
        status = {
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "progress": 0,
            "session_path": session_path,
            "original_filename": original_filename
        }
        training_sessions[session_id] = status
        save_session_metadata(session_id, status)

        # 1. Initial validation
        validation_results = validate_dataset(
            df_train, 
            training_params.datetime_column,
            training_params.target_column,
            training_params.item_id_column
        )
        
        if not validation_results["is_valid"]:
            error_message = "Данные не прошли валидацию: " + "; ".join(validation_results["errors"])
            raise ValueError(error_message)

        status.update({"progress": 10})
        save_session_metadata(session_id, status)
        
        # 2. Setup model directory
        model_path = get_model_path(session_id)
        os.makedirs(model_path, exist_ok=True)

        # Run the actual training process in a thread pool
        train_func = partial(
            train_model,
            df_train=df_train,
            training_params=training_params,
            model_path=model_path,
            session_id=session_id
        )
        
        await asyncio.to_thread(train_func)

        # Update final status
        status.update({
            "status": "completed",
            "end_time": datetime.now().isoformat(),
            "progress": 100,
            "model_path": model_path
        })
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status

    except Exception as e:
        error_msg = str(e)
        logging.error(f"Training error in session {session_id}: {error_msg}", exc_info=True)
        status = training_sessions[session_id]
        status.update({
            "status": "failed",
            "error": error_msg,
            "end_time": datetime.now().isoformat()
        })
        save_session_metadata(session_id, status)
        training_sessions[session_id] = status


def train_model(
    df_train: pd.DataFrame,
    training_params: TrainingParameters,
    model_path: str,
    session_id: str
) -> None:
    """Core training function that runs in a separate thread."""
    try:
        status = training_sessions[session_id]

        # 3. Data Preparation
        df2 = df_train.copy()
        df2[training_params.datetime_column] = pd.to_datetime(df2[training_params.datetime_column], errors="coerce")
        status.update({"progress": 20})
        save_session_metadata(session_id, status)

        # Add holidays if requested
        if training_params.use_russian_holidays:
            df2 = add_russian_holiday_feature(
                df2, 
                date_col=training_params.datetime_column, 
                holiday_col="russian_holiday"
            )
        status.update({"progress": 30})
        save_session_metadata(session_id, status)

        # Fill missing values
        df2 = fill_missing_values(
            df2,
            training_params.fill_missing_method,
            training_params.fill_group_columns
        )
        status.update({"progress": 40})
        save_session_metadata(session_id, status)

        # Handle static features
        static_df = None
        if training_params.static_feature_columns:
            tmp = df2[[training_params.item_id_column] + training_params.static_feature_columns].drop_duplicates(
                subset=[training_params.item_id_column]
            ).copy()
            tmp.rename(columns={training_params.item_id_column: "item_id"}, inplace=True)
            static_df = tmp

        # Convert to TimeSeriesDataFrame
        df_ready = safely_prepare_timeseries_data(
            df2,
            training_params.datetime_column,
            training_params.item_id_column,
            training_params.target_column
        )
        ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
        status.update({"progress": 50})
        save_session_metadata(session_id, status)

        # Handle frequency
        actual_freq = None
        if training_params.frequency and training_params.frequency.lower() != "auto":
            freq_short = training_params.frequency.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
            actual_freq = freq_short

        # Create predictor
        status.update({"progress": 60})
        save_session_metadata(session_id, status)
        
        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=training_params.prediction_length,
            eval_metric=training_params.evaluation_metric.split(" ")[0],
            freq=actual_freq,
            quantile_levels=[0.5] if training_params.predict_mean_only else None,
            path=model_path,
            verbosity=2
        )

        # Train the model
        status.update({"progress": 70})
        save_session_metadata(session_id, status)

        predictor.fit(
            train_data=ts_df,
            time_limit=training_params.training_time_limit,
            presets=training_params.autogluon_preset,
            hyperparameters=None if not training_params.models_to_train else {m: {} for m in training_params.models_to_train},
        )

        # Save model metadata
        model_metadata = training_params.model_dump()
        with open(os.path.join(model_path, "model_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(model_metadata, f, indent=2)

        status.update({"progress": 90})
        save_session_metadata(session_id, status)

        # Clean up
        del predictor
        gc.collect()

    except Exception as e:
        raise Exception(f"Error in training process: {str(e)}")


@router.get("/training_status/{session_id}")
async def get_session_status(session_id: str):
    """Get the status of a training session."""
    status = get_training_status(session_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Training session not found")
    return status


@router.post("/train_timeseries_model/")
async def train_model_endpoint(
    params: str = Form(...),
    training_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """Start an async training process and return a session ID for status tracking."""
    try:
        # Parse parameters
        params_dict = json.loads(params)
        training_params = TrainingParameters(**params_dict)
        
        # Validate file type
        if not training_file.filename.endswith((".csv", ".xlsx", ".xls")):
            raise HTTPException(
                status_code=400, 
                detail="Неверный тип файла. Пожалуйста, загрузите CSV или Excel файл."
            )

        # Create session ID and directory
        session_id = str(uuid.uuid4())
        session_path = create_session_directory(session_id)
        
        # Save the training file
        file_content = await training_file.read()
        training_file_path = save_training_file(session_id, file_content, training_file.filename)

        # Read the data
        try:
            if training_file.filename.endswith('.csv'):
                df_train = pd.read_csv(training_file_path)
            else:  # Excel file
                df_train = pd.read_excel(training_file_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

        # Initialize session status
        initial_status = {
            "status": "initializing",
            "create_time": datetime.now().isoformat(),
            "file_name": training_file.filename,
            "session_path": session_path,
            "progress": 0
        }
        training_sessions[session_id] = initial_status
        save_session_metadata(session_id, initial_status)

        # Start async training
        background_tasks.add_task(
            run_training_async,
            session_id,
            df_train,
            training_params,
            training_file.filename
        )

        return {
            "status": "accepted",
            "message": "Обучение запущено",
            "session_id": session_id
        }

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка разбора JSON параметров: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Ошибка валидации параметров: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при запуске обучения: {str(e)}"
        )
    finally:
        await training_file.close()