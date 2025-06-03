import json
import logging
import os
import pandas as pd
from typing import Any, Optional, List, Union
from pycaret.time_series import setup, compare_models, finalize_model, save_model, load_model, predict_model, pull
from fastapi import HTTPException
from sessions.utils import get_session_path, load_session_metadata, save_session_metadata
from AutoML.automl import AutoMLStrategy
import numpy as np # Для np.nanmean
import threading

# Глобальный lock для PyCaret
pycaret_lock = threading.Lock()

class PyCaretStrategy(AutoMLStrategy):
    name = 'pycaret'

    def train(self,
              ts_df: pd.DataFrame,
              training_params,
              session_id: str):
        session_path = get_session_path(session_id)
        pycaret_model_path = os.path.join(session_path, 'pycaret')
        os.makedirs(pycaret_model_path, exist_ok=True)

        item_id_col = training_params.item_id_column
        datetime_col = training_params.datetime_column
        target_col = training_params.target_column
        eval_metric = training_params.evaluation_metric.split(' ')[0]
        fh = 3  # Можно сделать параметром
        session_seed = 123
        budget_time = training_params.training_time_limit

        # --- Логика выбора моделей ---
        pycaret_models = training_params.pycaret_models
        if not pycaret_models or (isinstance(pycaret_models, list) and len(pycaret_models) == 0):
            logging.warning('[PyCaretStrategy train] Не выбрано ни одной модели для обучения. Пропуск.')
            return
        use_all_models = pycaret_models == '*' or (isinstance(pycaret_models, str) and pycaret_models.strip() == '*')

        ts_df[datetime_col] = pd.to_datetime(ts_df[datetime_col])
        for col in training_params.static_feature_columns + [item_id_col]:
            if col in ts_df.columns:
                ts_df[col] = ts_df[col].astype('category')

        # Определяем колонки, которые нужно удалить (все, кроме даты, таргета и id)
        keep_cols = [datetime_col, target_col, item_id_col]
        drop_cols_all = [col for col in ts_df.columns if col not in keep_cols] + [item_id_col]

        unique_ids = ts_df[item_id_col].unique()
        metrics = []
        preds_list = []

        # --- Новый блок: захват лока один раз для всей сессии ---
        lock_acquired = pycaret_lock.acquire(blocking=False)
        meta = load_session_metadata(session_id)
        if not lock_acquired:
            # Лок занят, пишем pycaret_locked=True в metadata.json
            try:
                meta['pycaret_locked'] = True
                save_session_metadata(session_id, meta)
            except Exception as e:
                logging.warning(f"[PyCaretStrategy train] Не удалось записать pycaret_locked=True в metadata.json: {e}")
            # Ждём освобождения лока
            pycaret_lock.acquire()
            # После получения лока, снимаем pycaret_locked
            try:
                meta = load_session_metadata(session_id)
                meta['pycaret_locked'] = False
                save_session_metadata(session_id, meta)
            except Exception as e:
                logging.warning(f"[PyCaretStrategy train] Не удалось записать pycaret_locked=False в metadata.json: {e}")
        else:
            # Если лок сразу получен, явно пишем pycaret_locked=False
            try:
                meta['pycaret_locked'] = False
                save_session_metadata(session_id, meta)
            except Exception as e:
                logging.warning(f"[PyCaretStrategy train] Не удалось записать pycaret_locked=False в metadata.json: {e}")
        try:
            for unique_id in unique_ids:
                id_df = ts_df[ts_df[item_id_col] == unique_id].copy()
                # Удаляем все неключевые колонки
                id_df = id_df.drop(columns=drop_cols_all, errors='ignore')
                id_df = id_df.set_index(datetime_col)
                id_df = id_df.sort_index()
                # ...весь блок работы с PyCaret теперь под lock...
                s = setup(
                    data=id_df,
                    target=target_col,
                    fh=fh,
                    session_id=session_seed,
                    numeric_imputation_target='ffill',
                    numeric_imputation_exogenous='ffill',
                    verbose=False,
                )
                if use_all_models:
                    best_model = compare_models(sort=eval_metric, fold=3, budget_time=budget_time / 60 / len(unique_ids) if budget_time else None, exclude="auto_arima")
                else:
                    best_model = compare_models(sort=eval_metric, fold=3, budget_time=budget_time / 60 / len(unique_ids) if budget_time else None, include=pycaret_models)

                leaderboard_df = pull()
                # Сохраняем leaderboard для каждого unique_id в отдельную папку
                id_leaderboards_dir = os.path.join(pycaret_model_path, 'id_leaderboards')
                os.makedirs(id_leaderboards_dir, exist_ok=True)
                leaderboard_save_path = os.path.join(id_leaderboards_dir, f'leaderboard_{unique_id}.csv')
                # Оставляем только нужные колонки
                metric_col = eval_metric.upper()
                leaderboard_to_save = leaderboard_df[[col for col in ['Model', metric_col] if col in leaderboard_df.columns]].copy()
                leaderboard_to_save.to_csv(leaderboard_save_path, index=False)
                best_score = leaderboard_to_save[metric_col][0] if metric_col in leaderboard_to_save.columns and not leaderboard_to_save.empty else None
                if best_score is not None:
                    metrics.append(best_score)
                finalized_model = finalize_model(best_model)
                preds = predict_model(finalized_model, fh=3)
                preds[item_id_col] = unique_id
                preds.reset_index(inplace=True)
                preds.rename(columns={preds.columns[0]: datetime_col}, inplace=True)
                preds_list.append(preds)

                logging.info(f"[PyCaretStrategy train] Finished {unique_id}, score: {metrics[-1]}")
        except Exception as e:
            logging.error(f"[PyCaretStrategy train] Error: {e}")
            raise
        finally:
            if pycaret_lock.locked():
                pycaret_lock.release()
                # После освобождения лока, явно пишем pycaret_locked=False
                try:
                    meta = load_session_metadata(session_id)
                    meta['pycaret_locked'] = False
                    save_session_metadata(session_id, meta)
                except Exception as e:
                    logging.warning(f"[PyCaretStrategy train] Не удалось записать pycaret_locked=False после release в metadata.json: {e}")
        # Сохраняем все прогнозы в один файл
        if preds_list:
            all_preds = pd.concat(preds_list, ignore_index=True)
            preds_path = os.path.join(pycaret_model_path, 'pycaret_predictions.csv')
            unnamed_cols = [col for col in all_preds.columns if str(col).startswith('Unnamed') or str(col).strip() == '']
            if unnamed_cols:
                all_preds = all_preds.drop(columns=unnamed_cols)
            if 'index' in all_preds.columns:
                all_preds = all_preds.drop(columns=['index'])
            if 'y_pred' in all_preds.columns:
                all_preds = all_preds.rename(columns={'y_pred': target_col})
            all_preds = all_preds[[datetime_col, target_col, item_id_col]]
            all_preds.to_csv(preds_path, index=False)
            logging.info(f"[PyCaretStrategy train] All predictions saved to: {preds_path}")
        avg_metric = -float(np.sum(metrics)) if metrics else 0
        self.save_pycaret_data(None, pycaret_model_path, training_params, avg_metric, eval_metric)
        logging.info(f"[PyCaretStrategy train] PyCaret training process completed for session {session_id}. Avg metric: {avg_metric}")

    def save_pycaret_data(self,
                          model: Any,
                          model_dir_path: str,
                          training_params,
                          avg_metric: float,
                          evaluation_metric_name: str):
        leaderboard_df = pd.DataFrame({'model': ['pycaret'], 'score_val': [avg_metric]})
        leaderboard_csv_path = os.path.join(model_dir_path, "leaderboard.csv")
        try:
            leaderboard_df.to_csv(leaderboard_csv_path, index=False)
            logging.info(f"[PyCaretStrategy save_data] Leaderboard saved to: {leaderboard_csv_path}")
        except Exception as e:
            logging.error(f"[PyCaretStrategy save_data] Error saving leaderboard.csv: {e}")
        
        model_metadata = training_params.model_dump()
        metadata_path = os.path.join(model_dir_path, "model_metadata.json")
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(model_metadata, f, indent=2, default=str)
            logging.info(f"[PyCaretStrategy save_data] Model metadata saved to: {metadata_path}")
        except Exception as e:
            logging.error(f"[PyCaretStrategy save_data] Error saving model_metadata.json: {e}")

    def predict(self,
                ts_df: Optional[pd.DataFrame], 
                session_id: str,
                training_params) -> pd.DataFrame:
        session_path = get_session_path(session_id)
        pycaret_model_dir = os.path.join(session_path, 'pycaret')
        preds_path = os.path.join(pycaret_model_dir, 'pycaret_predictions.csv')
        if not os.path.exists(preds_path):
            logging.error(f"Predictions file not found: {preds_path}")
            raise HTTPException(status_code=404, detail="Predictions file not found")
        result = pd.read_csv(preds_path)
        # Определяем имена колонок из training_params (dict)
        id_col = training_params.get('item_id_column')
        dt_col = training_params.get('datetime_column')
        tgt_col = training_params.get('target_column')
        # Если все три колонки присутствуют в результате, переупорядочиваем
        if all(col in result.columns for col in [id_col, dt_col, tgt_col]):
            result = result[[id_col, dt_col, tgt_col]]

        if 'index' in result.columns:
            result = result.drop(columns=['index'])
        return result
    
pycaret_strategy = PyCaretStrategy()