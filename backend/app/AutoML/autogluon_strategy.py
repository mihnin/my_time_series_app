import json
import logging
import os
from typing import Any

from fastapi import HTTPException

from AutoML.automl import AutoMLStrategy
from src.data.data_processing import convert_to_timeseries
from src.data.data_processing import safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from sessions.utils import get_session_path
from training.model import TrainingParameters
from autogluon.timeseries import TimeSeriesPredictor
from AutoML.locks import global_automl_lock

class AutoGluonStrategy(AutoMLStrategy):
    name = 'autogluon'
    def train(self,
        ts_df: Any, # Prepared TimeSeriesDataFrame (AutoGluon) or pd.DataFrame (PyCaret)
        training_params: TrainingParameters,
        session_id: str, # For logging/status updates # To update overall progress
        ):
        # --- ReadWriteLock: AutoGluon захватывает read lock ---
        meta = None
        try:
            meta = None
            try:
                from sessions.utils import load_session_metadata, save_session_metadata
                meta = load_session_metadata(session_id)
            except Exception:
                pass
            lock_acquired = False
            # Пытаемся получить read lock без блокировки, если не получается — пишем pycaret_locked=True
            if global_automl_lock._read_ready.acquire(blocking=False):
                if not global_automl_lock._writer:
                    global_automl_lock._readers += 1
                    global_automl_lock._read_ready.release()
                    lock_acquired = True
                else:
                    global_automl_lock._read_ready.release()
            if not lock_acquired:
                # Лок занят PyCaret'ом, пишем pycaret_locked=True
                if meta is not None:
                    try:
                        meta['pycaret_locked'] = True
                        save_session_metadata(session_id, meta)
                    except Exception as e:
                        logging.warning(f"[AutoGluonStrategy train] Не удалось записать pycaret_locked=True в metadata.json: {e}")
                # Ждём освобождения PyCaret (write lock)
                global_automl_lock.acquire_read()
                # После получения лока, снимаем pycaret_locked
                if meta is not None:
                    try:
                        meta = load_session_metadata(session_id)
                        meta['pycaret_locked'] = False
                        save_session_metadata(session_id, meta)
                    except Exception as e:
                        logging.warning(f"[AutoGluonStrategy train] Не удалось записать pycaret_locked=False в metadata.json: {e}")
            else:
                # Если лок сразу получен, явно пишем pycaret_locked=False
                if meta is not None:
                    try:
                        meta['pycaret_locked'] = False
                        save_session_metadata(session_id, meta)
                    except Exception as e:
                        logging.warning(f"[AutoGluonStrategy train] Не удалось записать pycaret_locked=False в metadata.json: {e}")
            # --- Обучение модели AutoGluon под read lock ---
            # Handle static features
            static_df = None
            if training_params.static_feature_columns:
                tmp = ts_df[[training_params.item_id_column] + training_params.static_feature_columns].drop_duplicates(
                    subset=[training_params.item_id_column]
                ).copy()
                tmp.rename(columns={training_params.item_id_column: "item_id"}, inplace=True)
                static_df = tmp
                logging.info(f"[train_model] Добавлены статические признаки: {training_params.static_feature_columns}")

            # Convert to TimeSeriesDataFrame
            df_ready = safely_prepare_timeseries_data(
                ts_df,
                training_params.datetime_column,
                training_params.item_id_column,
                training_params.target_column
            )
            ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)

            logging.info(f"[train_model] Данные преобразованы в TimeSeriesDataFrame.")

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

            # --- Логика выбора моделей ---
            models_to_train = training_params.models_to_train
            if not models_to_train or (isinstance(models_to_train, list) and len(models_to_train) == 0):
                logging.warning('[AutoGluonStrategy train] Не выбрано ни одной модели для обучения. Пропуск.')
                return
            use_all_models = models_to_train == '*' or (isinstance(models_to_train, str) and models_to_train.strip() == '*')

            hyperparams = {}
            if not use_all_models:
                for model in models_to_train:
                    if model == 'Chronos':
                        print("Chronos is using pre-installed")
                        hyperparams["Chronos"] = [
                            {"model_path": "autogluon_models/chronos-bolt-base", "ag_args": {"name_suffix": "ZeroShot"}},
                            {"model_path": "autogluon_models/chronos-bolt-small", "ag_args": {"name_suffix": "ZeroShot"}},
                            {"model_path": "autogluon_models/chronos-bolt-small", "fine_tune": True, "ag_args": {"name_suffix": "FineTuned"}}
                        ]
                    else:
                        hyperparams[model] = {}
            else:
                hyperparams = None

            # Train the model
            logging.info(f"[train_model] Запуск обучения модели...")
            predictor.fit(
                train_data=ts_df,
                time_limit=training_params.training_time_limit,
                presets=training_params.autogluon_preset,
                hyperparameters=hyperparams
            )
            self.save_data(predictor, model_path, training_params)
        finally:
            # Освобождаем read lock
            global_automl_lock.release_read()
            # После освобождения лока, явно пишем pycaret_locked=False
            if meta is not None:
                try:
                    meta = load_session_metadata(session_id)
                    meta['pycaret_locked'] = False
                    save_session_metadata(session_id, meta)
                except Exception as e:
                    logging.warning(f"[AutoGluonStrategy train] Не удалось записать pycaret_locked=False после release в metadata.json: {e}")

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
    
    def predict(self, ts_df, session_id, training_params):
        
        session_path = get_session_path(session_id)
        autogluon_model_dir = os.path.join(session_path, 'autogluon')
        static_feats = training_params.get("static_feature_columns")
        id_col = training_params.get("item_id_column")
        dt_col = training_params.get("datetime_column")
        tgt_col = training_params.get("target_column")
        freq = training_params.get("frequency")
        static_df = None
        

        if static_feats:
            tmp = ts_df[[id_col] + static_feats].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col: "item_id"}, inplace=True)
            static_df = tmp
            logging.info(f"Добавлены статические признаки: {static_feats}")

        df_ready = convert_to_timeseries(ts_df, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
        

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
            # Переименование колонок или индексов item_id и timestamp
            if hasattr(preds, 'rename'):
                rename_dict = {}
                if 'item_id' in getattr(preds, 'columns', []):
                    rename_dict['item_id'] = id_col
                if 'timestamp' in getattr(preds, 'columns', []):
                    rename_dict['timestamp'] = dt_col
                if 'mean' in getattr(preds, 'columns', []):
                    rename_dict['mean'] = tgt_col
                if rename_dict:
                    preds = preds.rename(columns=rename_dict)
                # Если item_id или timestamp в индексе
                if hasattr(preds, 'index') and hasattr(preds.index, 'names'):
                    index_rename = {}
                    if 'item_id' in preds.index.names:
                        index_rename['item_id'] = id_col
                    if 'timestamp' in preds.index.names:
                        index_rename['timestamp'] = dt_col
                    if index_rename:
                        preds = preds.rename_axis(index=index_rename)
        except Exception as e:
            logging.error(f"Ошибка при прогнозировании: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка при прогнозировании: {e}")
        preds = preds.reset_index()
        preds[dt_col] = preds[dt_col].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Удалить колонку 'index' из preds, если она появилась после reset_index
        if 'index' in preds.columns:
            preds = preds.drop(columns=['index'])

        return preds
    
autogluon_strategy = AutoGluonStrategy()