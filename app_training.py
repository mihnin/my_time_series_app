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
                     fill_method="None", group_cols_for_fill=None, **kwargs):
    """Выполняет обучение модели с переданными параметрами"""
    try:
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
        
        # Обучаем модель
        predictor.fit(
            train_data=ts_df,
            hyperparameters=train_params.get("hyperparameters"),
            hyperparameter_tune_kwargs=train_params.get("hyperparameter_tune_kwargs"),
            time_limit=train_params.get("time_limit"),
            # Настройка валидации - для процентного разделения используем num_val_windows
            num_val_windows=1 if fixed_split else max(1, round(val_percent/10)),
            val_step_size=prediction_length if fixed_split else None,
            enable_ensemble=True
        )
        
        # Засекаем время обучения
        training_time = time.time() - start_time
        logging.info(f"Обучение модели завершено за {training_time:.2f} секунд")
        
        # Получаем и сохраняем результаты
        leaderboard = predictor.leaderboard(silent=True)
        
        # Пытаемся получить fit_summary, но обрабатываем возможные ошибки
        fit_summary = None
        try:
            fit_summary = predictor.fit_summary()
        except ValueError as ve:
            # Проверяем наличие специфической ошибки с day_of_week
            if "Cannot locate autogluon.timeseries.utils" in str(ve):
                error_msg = f"Не удалось получить fit_summary из-за проблемы с модулем: {str(ve)}"
                logging.warning(error_msg)
                logging.info("Продолжаем работу без fit_summary")
                # Сохраняем информацию об ошибке в результат
                training_result['module_error'] = error_msg
            else:
                # Для других ошибок ValueError логируем, но не прерываем работу
                error_msg = f"Ошибка при получении fit_summary: {str(ve)}"
                logging.warning(error_msg)
                training_result['module_error'] = error_msg
        except Exception as e:
            error_msg = f"Не удалось получить fit_summary: {str(e)}"
            logging.warning(error_msg)
            training_result['module_error'] = error_msg
        
        # Сохраняем метаданные модели
        model_metadata = {
            "model_path": model_path,
            "training_time": training_time,
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
            "fit_summary": fit_summary,  # Может быть None, если возникла ошибка
            "training_time": training_time,
            "best_model_name": best_model_name,
            "best_model_score": best_model_score,
            "model_metadata": model_metadata
        }
        
        # Очищаем память
        gc.collect()
        
        return training_result
        
    except Exception as e:
        logging.exception(f"Ошибка при обучении модели: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def run_training():
    """Запускает процесс обучения модели"""
    # Проверки входных данных
    if st.session_state.get("df") is None:
        st.error("❌ Ошибка: Датасет не загружен. Пожалуйста, загрузите датасет.")
        return
    
    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col = st.session_state.get("id_col_key")
    
    if dt_col == "<нет>" or tgt_col == "<нет>":
        st.error("❌ Ошибка: Не выбраны обязательные колонки (дата и target).")
        return
    
    # Получаем базовую частоту из отображаемого значения
    freq_display = st.session_state.get("freq_key", "auto (угадать)")
    freq = get_base_freq(freq_display)
    
    # Статические признаки (преобразуем в список)
    static_feats = st.session_state.get("static_feats_key", [])
    
    # Другие параметры
    time_limit = st.session_state.get("time_limit_key", 60)
    prediction_length = st.session_state.get("prediction_length_key", 10)
    use_holidays = st.session_state.get("use_holidays_key", False)
    mean_only = st.session_state.get("mean_only_key", False)
    metric_key = st.session_state.get("metric_key", "RMSE")
    presets_key = st.session_state.get("presets_key", "medium_quality")
    models_key = st.session_state.get("models_key", [])
    
    # Метод заполнения пропусков
    fill_method = st.session_state.get("fill_method_key", "None")
    group_cols_for_fill = st.session_state.get("group_cols_for_fill_key", [])
    
    # Отображаем прогресс-бар и сообщение
    with st.spinner("🔄 Обучение модели..."):
        try:
            # Прямой вызов функции обучения вместо добавления задачи в очередь
            result = _execute_training(
                df_train=st.session_state["df"],
                dt_col=dt_col,
                tgt_col=tgt_col,
                id_col=id_col if id_col != "<нет>" else None,
                static_feats=static_feats,
                freq=freq,
                prediction_length=prediction_length,
                time_limit=time_limit,
                use_holidays=use_holidays,
                mean_only=mean_only,
                metric_key=metric_key,
                presets_key=presets_key,
                models_opt=models_key,
                fill_method=fill_method,
                group_cols_for_fill=group_cols_for_fill
            )
            
            if result['success']:
                # Обновляем состояние приложения результатами обучения
                st.session_state['predictor'] = result.get('predictor')
                st.session_state['leaderboard'] = result.get('leaderboard')
                st.session_state['fit_summary'] = result.get('fit_summary')
                st.session_state['best_model_name'] = result.get('best_model_name')
                st.session_state['best_model_score'] = result.get('best_model_score')
                st.session_state['model_metadata'] = result.get('model_metadata')
                
                # Отображаем информацию о результатах в основной области
                st.success(f"✅ Модель успешно обучена за {result.get('training_time', 0):.2f} секунд!")
                st.info(f"Лучшая модель: **{result.get('best_model_name')}** | Оценка: **{result.get('best_model_score'):.6f}**")
                
                # Полноэкранное отображение лидерборда
                st.subheader("📊 Результаты всех моделей (лидерборд)")
                
                # Отображаем лидерборд как полноэкранную таблицу
                if 'leaderboard' in result:
                    # Форматируем лидерборд для лучшего отображения
                    leaderboard_df = result['leaderboard'].copy()
                    # Округляем числовые колонки для лучшего отображения
                    for col in leaderboard_df.select_dtypes(include=['float']).columns:
                        leaderboard_df[col] = leaderboard_df[col].round(6)
                    
                    # Отображаем таблицу на всю ширину экрана
                    st.dataframe(
                        leaderboard_df,
                        use_container_width=True,
                        height=400
                    )
                
                # Генерируем Excel для скачивания результатов
                from src.utils.exporter import generate_excel_buffer
                
                # Создаем структуру результата для новой версии функции generate_excel_buffer
                excel_result = {
                    'success': True,
                    'forecasts': {}
                }
                
                # Добавляем лидерборд в данные для Excel
                if 'leaderboard' in result:
                    excel_result['leaderboard'] = result['leaderboard']
                
                # Добавляем информацию об ошибках модуля, если они есть
                if 'module_error' in result:
                    excel_result['module_error'] = result['module_error']
                
                # Извлекаем и добавляем информацию о составе ансамблевой модели, если лучшая модель - ансамбль
                from src.utils.exporter import extract_ensemble_weights
                
                if 'predictor' in result and result['predictor'] is not None:
                    best_model = result.get('best_model_name', '')
                    if 'Ensemble' in best_model:
                        try:
                            ensemble_info = extract_ensemble_weights(result['predictor'])
                            if ensemble_info is not None:
                                excel_result['ensemble_info'] = ensemble_info
                                st.info("📊 Добавлена подробная информация о составе ансамблевой модели")
                        except Exception as e:
                            logging.warning(f"Не удалось извлечь информацию об ансамбле: {e}")
                
                # Создаем буфер с Excel-файлом
                excel_buffer = generate_excel_buffer(excel_result)
                
                st.download_button(
                    label="📥 Скачать результаты обучения в Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"training_results_{st.session_state['best_model_name']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_training_results"
                )
                
                # Если включен чекбокс "Обучение, Прогноз и Сохранение", автоматически запускаем прогноз
                if st.session_state.get('train_predict_save_checkbox', False):
                    st.info("🔄 Запуск прогнозирования...")
                    from app_prediction import run_prediction
                    run_prediction()
            else:
                # Задача завершилась с ошибкой
                st.error(f"❌ Ошибка при обучении модели: {result.get('error', 'Неизвестная ошибка')}")
        
        except Exception as e:
            st.error(f"❌ Произошла ошибка при обучении модели: {str(e)}")
            logging.exception(f"Ошибка при обучении модели: {e}")
            return