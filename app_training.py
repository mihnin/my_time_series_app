# app_training.py
import streamlit as st
import pandas as pd
import shutil
import logging
import time
import gc
import os

from autogluon.timeseries import TimeSeriesPredictor
import psutil

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries, safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from app_saving import save_model_metadata
from src.validation.data_validation import validate_dataset, display_validation_results
# Новые импорты
from src.utils.queue_manager import get_queue_manager, TaskPriority
from src.utils.session_manager import get_current_session_id, save_to_session
from src.utils.resource_monitor import get_resource_monitor
from src.components.queue_status import show_queue_status
from app_ui import get_base_freq
# Импорт функции для модификации гиперпараметров Chronos
from src.utils.chronos_models import modify_chronos_hyperparams

# Функция запуска обучения модели через очередь
def queue_training_task(training_params, force_run=False):
    """
    Добавляет задачу обучения модели в очередь
    
    Parameters:
    -----------
    training_params : dict
        Параметры для обучения модели
    force_run : bool, optional (default=False)
        Если True, игнорирует проверку ресурсов и принудительно добавляет задачу
    
    Returns:
    --------
    str or None
        ID задачи в очереди или None, если задачу не удалось добавить
    """
    # Получаем текущий ID сессии
    session_id = get_current_session_id()
    
    # Проверяем, можно ли добавить новую задачу (достаточно ли ресурсов)
    if not force_run:
        resource_monitor = get_resource_monitor()
        if not resource_monitor.can_accept_new_task():
            st.error("Система в данный момент перегружена. Пожалуйста, повторите попытку позже.")
            return None
    
    # Получаем менеджер очереди
    queue_manager = get_queue_manager()
    
    # Добавляем задачу обучения в очередь с высоким приоритетом
    task_id = queue_manager.add_task(
        session_id=session_id,
        func=_execute_training,
        training_params=training_params,
        priority=TaskPriority.HIGH
    )
    
    logging.info(f"Задача обучения добавлена в очередь, ID: {task_id}")
    
    # Сохраняем ID задачи в сессии для последующего отслеживания
    save_to_session('current_training_task_id', task_id)
    
    # Возвращаем ID задачи
    return task_id

# Фактическая реализация обучения
def _execute_training(df_train, dt_col, tgt_col, id_col, static_feats=None, freq=None, 
                     prediction_length=10, time_limit=60, use_holidays=False, mean_only=False, 
                     metric_key="RMSE", presets_key="medium_quality", models_opt=None, 
                     fill_method="None", group_cols_for_fill=None, chronos_model="bolt_small", 
                     use_chronos=False, **kwargs):
    """
    Обучение TimeSeriesPredictor на датасете
    
    Основные аргументы:
        df_train: pandas.DataFrame - датасет для обучения
        dt_col: str - колонка с датой/временем
        tgt_col: str - целевая колонка
        id_col: str - колонка с ID объекта (None для одного временного ряда)
        static_feats: list - список статических признаков
        freq: str - частота временного ряда
        prediction_length: int - горизонт прогнозирования
        chronos_model: str - название модели Chronos для использования
        use_chronos: bool - использовать ли модели Chronos

    Возвращает:
        dict - словарь с результатами обучения
    """
    try:
        # Импортируем gc для управления памятью
        import gc
        
        # Инициализируем списки и словари, если нужно
        if static_feats is None:
            static_feats = []
        if models_opt is None:
            models_opt = []
        if group_cols_for_fill is None:
            group_cols_for_fill = []
            
        # Логируем начало процесса обучения
        logging.info(f"Начало выполнения обучения модели")
        logging.info(f"Параметры обучения: dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}, "
                    f"horizon={prediction_length}, presets={presets_key}, metric={metric_key}")
        
        # Добавляем признак с праздниками если нужно
        if use_holidays:
            df_train = add_russian_holiday_feature(df_train, dt_col)
            logging.info("Добавлен признак с российскими праздниками")
        
        # Заполняем пропуски, если нужно
        if fill_method != "None":
            logging.info(f"Заполнение пропусков методом {fill_method}")
            df_train = fill_missing_values(df_train, method=fill_method, group_cols=group_cols_for_fill)
        
        # Подготовка данных для обучения
        df_with_features = df_train.copy()
        
        # Сначала преобразуем датафрейм в формат с нужными именами колонок
        df_formatted = convert_to_timeseries(
            df_with_features, 
            id_col=id_col, 
            timestamp_col=dt_col, 
            target_col=tgt_col
        )
        
        # Проверяем, что все нужные колонки есть в данных
        if "item_id" not in df_formatted.columns:
            raise ValueError(f"Колонка ID 'item_id' не найдена в данных после преобразования")
        if "timestamp" not in df_formatted.columns:
            raise ValueError(f"Колонка даты 'timestamp' не найдена в данных после преобразования")
        if "target" not in df_formatted.columns:
            raise ValueError(f"Целевая колонка 'target' не найдена в данных после преобразования")
        
        logging.info(f"Исходная целевая колонка '{tgt_col}' переименована в 'target' в процессе преобразования")
        logging.info(f"Колонки в данных после преобразования: {list(df_formatted.columns)}")
        
        # Получаем или создаем статические признаки, если они есть
        static_df = None

        if static_feats and len(static_feats) > 0:
            # Выделяем статические признаки в отдельный DataFrame
            logging.info(f"Используются статические признаки: {static_feats}")
            static_cols = [col for col in df_with_features.columns if col in static_feats]
            if static_cols:
                static_df = df_with_features[[id_col] + static_cols].drop_duplicates(id_col).copy()
                static_df.rename(columns={id_col: "item_id"}, inplace=True)
                static_df.set_index("item_id", inplace=True)
                logging.info(f"Создан DataFrame статических признаков с колонками: {list(static_df.columns)}")

        # Изменяем как преобразуется частота из пользовательского интерфейса
        base_freq = get_base_freq(freq)
        logging.info(f"Используется частота: {base_freq}")

        # Если это 'auto', заменяем на 'D' для надежности
        if base_freq == 'auto':
            logging.warning("Автоматическое определение частоты отключено, используется 'D' (день)")
            base_freq = 'D'
        
        # Используем теперь base_freq вместо auto-detect при создании TimeSeriesDataFrame
        ts_df = make_timeseries_dataframe(
            df_formatted,
            static_features=static_df,
            freq=base_freq  # Явно указываем частоту
        )
        
        # Сохраняем вычисленную частоту для дальнейшего использования
        training_result = {'actual_freq': base_freq}
        
        # Детальное логирование информации о частоте
        logging.info(f"Используемая частота данных: {base_freq}")
        if base_freq == "auto":
            logging.warning("Автоматическое определение частоты может вызвать ошибку. Рекомендуется явно указать частоту.")
        
        # Настраиваем параметры обучения
        train_params = {
            "eval_metric": metric_key,
            "prediction_length": prediction_length
        }
        
        # Извлекаем короткую версию метрики (до пробела или скобки)
        short_metric = metric_key.split(" ")[0] if " " in metric_key else metric_key
        logging.info(f"Используется метрика '{short_metric}' (из '{metric_key}')")
        
        # Конфигурация для разных пресетов качества
        presets_config = {
            "fast_training": {
                "hyperparameters": {"SeasonalNaiveModel": {}},
                "hyperparameter_tune_kwargs": None,
                "time_limit": 60
            },
            "medium_quality": {
                "hyperparameters": None,
                "hyperparameter_tune_kwargs": None,
                "time_limit": 300
            },
            "high_quality": {
                "hyperparameters": None,
                "hyperparameter_tune_kwargs": None,
                "time_limit": 600
            },
            "best_quality": {
                "hyperparameters": None,
                "hyperparameter_tune_kwargs": None,
                "time_limit": 1800
            }
        }
        
        # Применяем выбранный пресет
        preset_config = presets_config.get(presets_key, presets_config["medium_quality"])
        for key, value in preset_config.items():
            train_params[key] = value
        
        # Если выбраны конкретные модели, добавляем их
        if models_opt and "* (все)" not in models_opt:
            # Вместо included_model_types используем hyperparameters для ограничения моделей
            if train_params.get("hyperparameters") is None:
                train_params["hyperparameters"] = {}
            
            # Добавляем только выбранные модели в hyperparameters
            for model in models_opt:
                train_params["hyperparameters"][model] = {}
            
            logging.info(f"Выбранные модели для обучения настроены через hyperparameters: {models_opt}")
        
        # Если выбраны статические признаки
        if static_feats:
            train_params["static_features"] = static_feats
            logging.info(f"Используются статические признаки: {static_feats}")
        
        # Определяем, нужно ли использовать валидационное разделение
        if 'validation_split' in kwargs:
            validation_split = kwargs['validation_split']
        else:
            validation_split = 10  # По умолчанию 10%
        
        # Определяем тип разделения на основе validation_split
        if isinstance(validation_split, int) or isinstance(validation_split, float):
            # Процентное разделение
            split_mode = f"percent_{validation_split}"
        else:
            # Фиксированное разделение (по умолчанию)
            split_mode = "fixed"
        
        # Фиксированное или процентное разделение
        fixed_split = split_mode.startswith("fixed")
        
        if fixed_split:
            # Фиксированное разделение
            num_samples = len(df_formatted["timestamp"].unique()) 
            split_idx = num_samples - prediction_length
            
            # При фиксированном разделении можно использовать num_val_windows=1 по умолчанию
            logging.info(f"Используется фиксированное разделение данных: последние {prediction_length} шагов")
        else:
            # Процентное разделение: настраиваем через num_val_windows и val_step_size
            val_percent = int(split_mode.replace("percent_", ""))
            logging.info(f"Используется процентное разделение данных: {val_percent}%")
        
        # Создаем директорию для модели, если её нет
        model_path = "AutogluonModels/TimeSeriesModel"
        os.makedirs(model_path, exist_ok=True)
        
        # Логируем начало обучения
        start_time = time.time()
        logging.info(f"Начало обучения модели с параметрами: {train_params}")
        
        # Создаем и обучаем предиктор
        predictor = TimeSeriesPredictor(
            prediction_length=prediction_length,
            target="target",
            eval_metric=short_metric,
            path=model_path,
            freq=base_freq if base_freq != "auto" else None
        )
        
        # Получаем базовые hyperparameters
        base_hyperparams = train_params.get("hyperparameters", {}) or {}
        
        # Создаем словарь для моделей, начиная с моделей, выбранных пользователем
        model_hyperparams = base_hyperparams.copy() if base_hyperparams else {}
        
        # Добавляем Chronos только если use_chronos=True
        if use_chronos:
            model_hyperparams["Chronos"] = modify_chronos_hyperparams(chronos_model, {})
            logging.info(f"Добавлена модель Chronos ({chronos_model}) к списку моделей для обучения")
        
        # Обучаем модель
        predictor.fit(
            train_data=ts_df,
            hyperparameters=model_hyperparams,
            hyperparameter_tune_kwargs=train_params.get("hyperparameter_tune_kwargs"),
            time_limit=train_params.get("time_limit"),
            # Настройка валидации - для процентного разделения используем num_val_windows
            num_val_windows=1 if 'percent' in split_mode else 0,
            enable_ensemble=True  # Включаем построение ансамблевой модели
        )
        
        # Логируем информацию о затраченном времени
        train_time = time.time() - start_time
        logging.info(f"Обучение завершено за {train_time:.2f} секунд")
        
        # Получаем fit_summary для информации о процессе обучения
        try:
            fit_summary = predictor.fit_summary()
            logging.info(f"Fit summary: {fit_summary}")
            training_result["fit_summary"] = fit_summary
        except Exception as e:
            logging.warning(f"Не удалось получить fit_summary: {e}")
            training_result["fit_summary"] = {"error": str(e)}
        
        # Получаем и сохраняем результаты
        leaderboard = predictor.leaderboard(silent=True)
        
        # Сохраняем метаданные модели
        model_metadata = {
            "model_path": model_path,
            "training_time": train_time,
            "dt_col": dt_col,
            "tgt_col": tgt_col,
            "id_col": id_col,
            "freq": base_freq,
            "horizon": prediction_length,
            "use_holidays": use_holidays,
            "static_features": static_feats,
            "metric": metric_key,
            "preset": presets_key,
        }
        
        # Определяем лучшую модель
        best_model = leaderboard.iloc[0]
        best_model_name = best_model["model"]
        best_model_score = best_model["score_val"]
        
        # Добавляем информацию о лучшей модели
        model_metadata["best_model"] = {
            "name": best_model_name,
            "score": best_model_score,
            "metric": metric_key
        }
        
        # Сохраняем метаданные в файл
        save_model_metadata(model_metadata)
        
        # Формируем результат выполнения задачи
        training_result = {
            "success": True,
            "predictor": predictor,
            "leaderboard": leaderboard,
            "fit_summary": training_result["fit_summary"],
            "training_time": train_time,
            "best_model_name": best_model_name,
            "best_model_score": best_model_score,
            "model_metadata": model_metadata
        }
        
        # Освобождаем память от временных данных
        if 'static_df' in locals() and static_df is not None:
            del static_df
        if 'df_formatted' in locals():
            del df_formatted
        gc.collect()
        
        return training_result
    except Exception as e:
        logging.exception(f"Ошибка при обучении модели: {e}")
        
        # Обрабатываем специфичные ошибки для моделей Chronos
        error_message = str(e)
        error_details = {
            "success": False,
            "error": error_message
        }
        
        # Проверяем наличие специфичных ошибок для моделей Chronos
        if "model_path" in error_message and ("chronos" in error_message.lower() or "bolt" in error_message.lower()):
            logging.error(f"Ошибка при загрузке модели Chronos: {e}")
            error_details["error_type"] = "chronos_model_loading"
            error_details["error_description"] = "Не удалось загрузить модель Chronos. Проверьте наличие локальных моделей или доступ к Hugging Face."
        elif "transformers" in error_message.lower() and "huggingface" in error_message.lower():
            logging.error(f"Ошибка при доступе к Hugging Face: {e}")
            error_details["error_type"] = "huggingface_access"
            error_details["error_description"] = "Невозможно загрузить модель с Hugging Face. Проверьте подключение к интернету или наличие локальных моделей."
        elif "cuda" in error_message.lower() or "gpu" in error_message.lower():
            logging.error(f"Ошибка при использовании CUDA/GPU: {e}")
            error_details["error_type"] = "gpu_error"
            error_details["error_description"] = "Проблема с доступом к GPU. Попробуйте использовать CPU-версию модели."
        elif "fine_tune" in error_message.lower() or "fine-tuning" in error_message.lower():
            logging.error(f"Ошибка при fine-tuning модели Chronos: {e}")
            error_details["error_type"] = "fine_tuning_error"
            error_details["error_description"] = "Проблема при дообучении модели Chronos. Проверьте параметры fine-tuning."
        
        # Освобождаем память после ошибки
        gc.collect()
        return error_details

def run_training(
    df_train, dt_col, tgt_col, horizon, id_col=None, scaler_type="standard", 
    models=None, eval_metric=None, time_limit=300, freq=None, 
    num_samples=None, target_quantiles=None, ensemble=False,
    model_hyperparameters=None, additional_hyperparameters=None,
    use_chronos=False, chronos_model=None, allow_download=True
):
    """
    Запускает процесс обучения модели с заданными параметрами
    
    Аргументы:
        df_train: датафрейм для обучения
        dt_col: колонка с датой/временем
        tgt_col: целевая колонка
        horizon: горизонт прогнозирования
        id_col: колонка с идентификатором временного ряда
        scaler_type: тип нормализации данных
        models: список моделей для обучения
        eval_metric: метрика для оценки
        time_limit: ограничение времени обучения
        freq: частота временного ряда
        use_chronos: использовать ли модели Chronos
        chronos_model: название модели Chronos
        allow_download: разрешить загрузку модели с Hugging Face
    
    Возвращает:
        bool: успешность обучения
    """
    import gc
    import logging
    import streamlit as st
    
    # Создаем элементы интерфейса для отображения прогресса
    training_task = st.empty()
    training_progress_bar = st.empty()
    
    with training_task:
        st.info("🔄 Запуск обучения модели...")
    
    try:
        with training_progress_bar:
            st.progress(0.1, text="Подготовка данных для обучения...")
            
            # Здесь происходит вызов функции _execute_training с параметрами
            result = _execute_training(
                df_train=df_train,
                dt_col=dt_col,
                tgt_col=tgt_col,
                id_col=id_col,
                prediction_length=horizon,
                time_limit=time_limit,
                freq=freq,
                models_opt=models,
                metric_key=eval_metric if eval_metric else "RMSE",
                fill_method="None",
                static_feats=[],
                use_chronos=use_chronos,
                chronos_model=chronos_model if chronos_model else "bolt_small"
            )
            
            # Проверяем результат обучения
            if result['success']:
                # Обновляем состояние приложения результатами обучения
                st.session_state['predictor'] = result.get('predictor')
                st.session_state['leaderboard'] = result.get('leaderboard')
                st.session_state['fit_summary'] = result.get('fit_summary')
                st.session_state['best_model_name'] = result.get('best_model_name')
                st.session_state['best_model_score'] = result.get('best_model_score')
                st.session_state['model_metadata'] = result.get('model_metadata')
                
                # Обновляем интерфейс
                st.success(f"✅ Модель успешно обучена за {result.get('training_time', 0):.2f} секунд!")
                st.info(f"Лучшая модель: **{result.get('best_model_name')}** | Оценка: **{result.get('best_model_score'):.6f}**")
                
                # Возвращаем True, что означает успех
                return True
            else:
                # Если обучение не удалось, показываем сообщение об ошибке
                error_message = result.get('error', 'Неизвестная ошибка')
                st.error(f"❌ Ошибка при обучении модели: {error_message}")
                return False
                
    except Exception as e:
        # Логируем ошибку
        logging.error(f"Ошибка при обучении модели: {e}", exc_info=True)
        
        # Обновляем интерфейс
        st.error(f"Ошибка при обучении модели: {str(e)}")
        st.error("Проверьте логи для получения более подробной информации")
        
        # Обновляем статус задачи
        with training_task:
            st.error("❌ Обучение завершилось с ошибкой")
        
        # Освобождаем память
        del df_train
        gc.collect()
        
        # Возвращаем False, что означает ошибку
        return False