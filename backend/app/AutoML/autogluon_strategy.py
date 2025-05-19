import json
import logging
import os
from typing import Any

from fastapi import HTTPException

from AutoML.automl import AutoMLStrategy
from sessions.utils import get_session_path
from training.model import TrainingParameters
from autogluon.timeseries import TimeSeriesPredictor

class AutoGluonStrategy(AutoMLStrategy):
    name = 'autogluon'
    def train(self,
        ts_df: Any, # Prepared TimeSeriesDataFrame (AutoGluon) or pd.DataFrame (PyCaret)
        training_params: TrainingParameters,
        session_id: str, # For logging/status updates # To update overall progress
        ):

        session_path = get_session_path(session_id)
        
        logging.info(f"[train_model] Создание объекта TimeSeriesPredictor...")
        model_path =  os.path.join(session_path, 'autogluon')
        actual_freq = training_params.frequency.split(" ")[0]

        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=training_params.prediction_length,
            eval_metric=training_params.evaluation_metric.split(" ")[0],
            freq=actual_freq,
            quantile_levels=[0.5] if training_params.predict_mean_only else None,
            path=model_path,
            verbosity=2
        )

        hyperparams = {}

        if training_params.models_to_train:
            for model in training_params.models_to_train:
                if model == 'Chronos':
                    print("Chronos is using pre-installed" )
                    hyperparams["Chronos"] = [
                        {"model_path": "autogluon/chronos-bolt-base", "ag_args": {"name_suffix": "ZeroShot"}},
                        {"model_path": "autogluon/chronos-bolt-small", "ag_args": {"name_suffix": "ZeroShot"}},
                        {"model_path": "autogluon/chronos-bolt-small", "fine_tune": True, "ag_args": {"name_suffix": "FineTuned"}}
                    ]
                else:
                    hyperparams[model] = {}

        # Train the model
        logging.info(f"[train_model] Запуск обучения модели...")
        predictor.fit(
            train_data=ts_df,
            time_limit=training_params.training_time_limit,
            presets=training_params.autogluon_preset,
            hyperparameters=None if not hyperparams else hyperparams,
        )
        self.save_data(predictor, model_path, training_params)

    def save_data(self, predictor, model_path, training_params):

        leaderboard_df = predictor.leaderboard(silent=True)
        leaderboard_path = os.path.join(model_path, "leaderboard.csv")
        leaderboard_df.to_csv(leaderboard_path, index=False)
        logging.info(f"[train_model] Лидерборд сохранён: {leaderboard_path}")

        # Save model metadata, including WeightedEnsemble weights if present
        model_metadata = training_params.model_dump()
        # Check for WeightedEnsemble in leaderboard
        if "WeightedEnsemble" in leaderboard_df["model"].values:
            try:
                weighted_ensemble_model = predictor._trainer.load_model("WeightedEnsemble")
                model_to_weight = getattr(weighted_ensemble_model, "model_to_weight", None)
                if model_to_weight is not None:
                    print(model_to_weight)
                    model_metadata["weightedEnsemble"] = model_to_weight
            except Exception as e:
                logging.warning(f"[train_model] Не удалось получить веса WeightedEnsemble: {e}")

        with open(os.path.join(model_path, "model_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(model_metadata, f, indent=2)

        logging.info(f"[train_model] Метаданные модели сохранены.")
    
    def predict(self, ts_df, session_id):
        session_path = get_session_path(session_id)
        model_path = os.path.join(session_path, "autogluon")
        if not os.path.exists(model_path):
            logging.error(f"Папка с моделью не найдена: {model_path}")
            raise HTTPException(status_code=404, detail="Папка с моделью не найдена")
        try:
            predictor = TimeSeriesPredictor.load(model_path)
            logging.info(f"Модель успешно загружена из {model_path}")
        except Exception as e:
            logging.error(f"Ошибка загрузки модели: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка загрузки модели: {e}")

        
        # 6. Прогноз
        try:
            preds = predictor.predict(ts_df)
            logging.info(f"Прогноз успешно выполнен для session_id={session_id}")
        except Exception as e:
            logging.error(f"Ошибка при прогнозировании: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при прогнозировании: {e}")
        
        return preds

autogluon_strategy = AutoGluonStrategy()