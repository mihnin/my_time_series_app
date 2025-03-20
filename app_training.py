# app_training.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import logging
import os
from datetime import datetime
from pathlib import Path
import plotly.express as px

from app_ui import display_error_message, METRICS_DICT, FREQ_REVERSE_MAPPING

from src.utils.config import (
    TIMESERIES_MODELS_DIR, MODEL_METADATA_FILE, LOGS_DIR,
    DEFAULT_CHUNK_SIZE, DEFAULT_PREDICTION_LENGTH, DEFAULT_TIME_LIMIT,
    MAX_VISUALIZE_POINTS
)
from src.models.forecasting import (
    make_timeseries_dataframe, train_model, extract_model_metrics, forecast, convert_predictions_to_dataframe, get_model_performance
)
from src.validation.data_validation import validate_forecasting_data, display_validation_results
from app_saving import save_model_metadata

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'app_training.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация директорий
os.makedirs(TIMESERIES_MODELS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Функции для работы с интерфейсом
def show_dataframe_info(df):
    """Отображает информацию о DataFrame"""
    if df is None or df.empty:
        st.warning("Данные не загружены или пусты")
        return
    
    st.write(f"Размер набора данных: {df.shape[0]} строк, {df.shape[1]} столбцов")
    
    # Отображаем выборку данных
    st.subheader("Образец данных:")
    st.dataframe(df.head(10))
    
    # Отображаем уникальные идентификаторы
    if "item_id" in df.columns:
        unique_ids = df["item_id"].unique()
        st.write(f"Количество уникальных временных рядов (item_id): {len(unique_ids)}")
        
        if len(unique_ids) <= 10:
            st.write("Уникальные идентификаторы:", ", ".join(map(str, unique_ids)))
        else:
            st.write(f"Первые 10 из {len(unique_ids)} уникальных идентификаторов:", 
                     ", ".join(map(str, unique_ids[:10])))
    
    # Информация о датах
    if "timestamp" in df.columns:
        min_date = df["timestamp"].min()
        max_date = df["timestamp"].max()
        date_range = max_date - min_date
        st.write(f"Временной диапазон: от {min_date} до {max_date} (всего {date_range.days + 1} дней)")
    
    # Статистика числовых столбцов
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        st.subheader("Статистика числовых признаков:")
        stats_df = df[numeric_cols].describe().T
        st.dataframe(stats_df)

def save_model_metadata(model_name, info_dict):
    """Сохраняет метаданные модели в JSON-файл"""
    
    def convert_to_serializable(obj):
        """Превращает не-JSON-сериализуемые объекты в строки"""
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            return obj.to_dict()
        try:
            # Пробуем сначала простую сериализацию
            json.dumps(obj)
            return obj
        except (TypeError, OverflowError):
            # Если объект не сериализуемый, преобразуем его в строку
            return str(obj)
    
    # Рекурсивно проходим по всему словарю и конвертируем объекты
    def make_serializable(d):
        if isinstance(d, dict):
            return {k: make_serializable(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [make_serializable(item) for item in d]
        else:
            return convert_to_serializable(d)
    
    # Конвертируем все метаданные в сериализуемый формат
    serializable_info = make_serializable(info_dict)
    
    metadata_file = Path(MODEL_METADATA_FILE)
    
    # Загружаем существующие метаданные или создаем новый словарь
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Ошибка при чтении файла метаданных {metadata_file}. Создаем новый.")
            metadata = {}
    else:
        metadata = {}
    
    # Добавляем метаданные текущей модели
    metadata[model_name] = serializable_info
    
    # Сохраняем обновленные метаданные
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    
    logger.info(f"Метаданные модели {model_name} сохранены в {metadata_file}")

def display_training_parameters():
    """Отображает и собирает параметры для обучения модели"""
    with st.expander("Параметры обучения", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Общие параметры
            model_name = st.text_input("Название модели", 
                                      value=f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            prediction_length = st.number_input("Горизонт прогнозирования (количество шагов вперед)", 
                                               min_value=1, value=DEFAULT_PREDICTION_LENGTH)
            
            time_limit = st.number_input("Ограничение времени обучения (секунд)", 
                                        min_value=60, value=DEFAULT_TIME_LIMIT)
            
            freq_options = {
                "auto (угадать)": None, 
                "Дни (D)": "D", 
                "Часы (H)": "H", 
                "15 минут (15min)": "15min",
                "Минуты (min)": "min", 
                "Месяцы (M)": "M"
            }
            freq = st.selectbox("Частота данных", options=list(freq_options.keys()))
            freq_value = freq_options[freq]
            
        with col2:
            # Дополнительные параметры
            fill_method_options = {
                "None": None,
                "forward fill (ffill)": "ffill",
                "backward fill (bfill)": "bfill",
                "Среднее (mean)": "mean", 
                "Медиана (median)": "median", 
                "Нулевые значения (zeros)": "zeros"
            }
            fill_method = st.selectbox("Метод заполнения пропусков", 
                                      options=list(fill_method_options.keys()))
            fill_method_value = fill_method_options[fill_method]
            
            metric_options = {
                "MASE (Mean absolute scaled error)": "MASE",
                "RMSE (Root mean squared error)": "RMSE", 
                "MAE (Mean absolute error)": "MAE", 
                "MAPE (Mean absolute percentage error)": "MAPE", 
                "sMAPE (Symmetric MAPE)": "sMAPE",
                "WAPE (Weighted absolute percentage error)": "WAPE",
                "MSE (Mean squared error)": "MSE"
            }
            eval_metric = st.selectbox("Метрика оценки", options=list(metric_options.keys()))
            eval_metric_value = metric_options[eval_metric]
            
            preset_options = {
                "medium_quality": "medium_quality (баланс качества и скорости)",
                "high_quality": "high_quality (лучшее качество, но дольше)",
                "best_quality": "best_quality (максимальное качество, очень долго)",
                "fast_training": "fast_training (быстрое обучение, ниже качество)"
            }
            preset = st.selectbox("Пресет AutoGluon", 
                                 options=list(preset_options.values()))
            preset_value = [k for k, v in preset_options.items() if v == preset][0]
            
            # Чтобы отобразить более крупно и явно важный выбор модели
            model_types = ["DeepAR", "Chronos", "ETS", "Prophet", "PatchTST", "* (все)"]
            selected_models = st.multiselect(
                "Выбор моделей для обучения",
                options=model_types,
                default=["Chronos", "Prophet"]
            )
    
    # Дополнительные расширенные параметры
    with st.expander("Расширенные параметры", expanded=False):
        use_gpu = st.checkbox("Использовать GPU (при наличии)", value=True)
        
        # Параметры предобработки
        col1, col2 = st.columns(2)
        with col1:
            chunk_size = st.number_input("Размер чанка (для больших данных)", 
                                        min_value=1000, value=DEFAULT_CHUNK_SIZE)
            target_column = st.text_input("Целевая переменная (target)", value="target")
            
        with col2:
            timestamp_column = st.text_input("Столбец с временными метками", value="timestamp")
            id_column = st.text_input("Столбец с идентификаторами рядов", value="item_id")
    
    # Возвращаем собранные параметры обучения
    return {
        "model_name": model_name,
        "prediction_length": prediction_length,
        "time_limit": time_limit,
        "freq": freq_value,
        "fill_method": fill_method_value,
        "eval_metric": eval_metric_value,
        "preset": preset_value,
        "selected_models": selected_models if selected_models else ["all"],
        "use_gpu": use_gpu,
        "chunk_size": chunk_size,
        "target_column": target_column,
        "timestamp_column": timestamp_column,
        "id_column": id_column
    }

def run_training(df_train=None, dt_col=None, tgt_col=None, horizon=None, id_col=None, 
               freq=None, models=None, eval_metric=None, time_limit=300, 
               use_chronos=False, chronos_model=None):
    """
    Точка входа для модуля обучения моделей.
    Эта функция вызывается из основного приложения (app.py).
    
    Args:
        df_train (pd.DataFrame, optional): DataFrame с данными для обучения
        dt_col (str, optional): Название колонки с временной меткой
        tgt_col (str, optional): Название колонки с целевой переменной
        horizon (int, optional): Горизонт прогноза
        id_col (str, optional): Название колонки с идентификатором ряда
        freq (str, optional): Частота данных (D, H, M, и т.д.)
        models (str, optional): Какие модели использовать ('all', 'deepar', и т.д.)
        eval_metric (str, optional): Метрика для оценки (RMSE, MAE, и т.д.)
        time_limit (int, optional): Ограничение времени на обучение в секундах
        use_chronos (bool, optional): Использовать ли Chronos модели
        chronos_model (str, optional): Какую Chronos модель использовать
    """
    # Если данные не переданы, запускаем основную интерактивную логику
    if df_train is None:
        main()
        return
    
    # Иначе выполняем непосредственное обучение с переданными параметрами
    st.title("Обучение модели для прогнозирования временных рядов")
    
    try:
        # Конвертируем полное название метрики в короткое (требуется для AutoGluon)
        short_metric = eval_metric
        if eval_metric in METRICS_DICT:
            short_metric = METRICS_DICT[eval_metric]
        else:
            # Если метрика не найдена в словаре, проверяем, может быть это уже короткая форма
            valid_short_metrics = set(METRICS_DICT.values())
            if eval_metric not in valid_short_metrics:
                st.warning(f"Предупреждение: метрика {eval_metric} не распознана. Используем RMSE по умолчанию.")
                short_metric = "RMSE"
        
        # Используем переданное значение частоты
        # Переменная freq_value доступна только при вызове из интерфейса, не при прямом вызове функции
        base_freq = freq  # Используем аргумент функции вместо переменной из GUI

        # Выводим информацию о параметрах
        st.write("### Параметры обучения")
        params_df = pd.DataFrame({
            "Параметр": ["Временная метка", "Целевая переменная", "ID ряда", "Горизонт прогноза", 
                        "Частота", "Модели", "Метрика", "Ограничение времени"],
            "Значение": [dt_col, tgt_col, id_col, horizon, 
                        freq, models, eval_metric, f"{time_limit} сек"]
        })
        st.dataframe(params_df)
        
        # Показываем данные
        with st.expander("Данные для обучения", expanded=False):
            st.dataframe(df_train.head(10))
            st.write(f"Размер данных: {df_train.shape}")
        
        # Настраиваем данные для TimeSeriesDataFrame
        with st.spinner("Подготовка данных..."):
            # Создаем копию данных для преобразования
            df_copy = df_train.copy()
            
            # Если ID ряда не указан, используем один временной ряд
            if id_col is None:
                df_copy['item_id'] = 'series_0'
            else:
                # Переименовываем ID колонку
                df_copy.rename(columns={id_col: 'item_id'}, inplace=True)
            
            # Переименовываем остальные колонки для TimeSeriesDataFrame
            df_copy.rename(columns={
                dt_col: 'timestamp',
                tgt_col: 'target'
            }, inplace=True)
            
            # Создаем TimeSeriesDataFrame
            tsdf = make_timeseries_dataframe(
                df=df_copy,
                freq=base_freq,
                id_column='item_id',
                timestamp_column='timestamp',
                target_column='target'
            )
            
            # Теперь, когда tsdf создан, проверяем и логируем информацию о частоте
            base_freq = getattr(tsdf, 'freq', None)
            logging.info("Создание TimeSeriesDataFrame из набора данных размером %s", df_train.shape)
            logging.info("TimeSeriesDataFrame создан с частотой %s", base_freq if base_freq else 'не определена')
            logging.info("Количество рядов в TimeSeriesDataFrame: %s", len(tsdf))
            
            if len(tsdf) == 0:
                raise ValueError("TimeSeriesDataFrame не содержит данных")
                
            st.success(f"TimeSeriesDataFrame успешно создан, содержит {len(tsdf)} рядов")
            
            # Выводим идентификаторы рядов
            item_ids = tsdf.item_ids
            logging.info("Идентификаторы рядов: %s", item_ids[:5])
        
        # Настройка гиперпараметров и модели
        preset_to_use = "medium_quality" if time_limit > 600 else "fast_training"
        
        # По умолчанию используем "default" для активации всех моделей
        hyperparameters = "default"
        
        # Если указано значение hyperparameters="default", используем его напрямую
        if models and isinstance(models, list) and "default" in models:
            logging.info("Используется параметр hyperparameters='default' для включения всех доступных моделей")
            hyperparameters = "default"
        # Также проверяем, есть ли среди моделей "* (все)" или "all"
        elif models and isinstance(models, list) and ("* (все)" in models or "all" in models):
            logging.info("Используется параметр hyperparameters='default' для включения всех доступных моделей через '* (все)'")
            hyperparameters = "default"
        elif models:
            # Если в models передан список конкретных моделей, проверяем их
            valid_models = [
                'DeepAR', 'ARIMA', 'AutoARIMA', 'AutoETS', 'ETS', 'Theta', 
                'DirectTabular', 'RecursiveTabular', 'NPTS', 'PatchTST', 
                'DLinear', 'TiDE', 'TemporalFusionTransformer', 'Naive', 
                'SeasonalNaive', 'Average', 'SeasonalAverage', 'Chronos'
            ]
            
            # Фильтруем список моделей, оставляя только действительные
            if isinstance(models, list):
                selected_models = [model for model in models if model in valid_models]
                
                if selected_models:
                    # Используем только указанные модели, создавая словарь с пустыми настройками
                    hyperparameters = {model: {} for model in selected_models}
                    logging.info(f"Используются конкретные модели: {selected_models}")
                else:
                    # Если нет действительных моделей, используем "default"
                    hyperparameters = "default"
                    logging.info("В выборе нет действительных моделей, используется hyperparameters='default'")
        
        # Обработка Chronos отдельно
        if use_chronos:
            chronos_preset = chronos_model if chronos_model in ["bolt_tiny", "bolt_mini", "bolt_small", "bolt_base",
                                                                "chronos_tiny", "chronos_mini", "chronos_small", 
                                                                "chronos_base", "chronos_large", "chronos"] else "bolt_small"
            
            if hyperparameters == "default":
                # Если используем default, создаем словарь с одной моделью Chronos
                logging.info(f"Используется Chronos модель {chronos_preset} вместе с default гиперпараметрами")
            else:
                # Если уже есть словарь моделей, добавляем к нему Chronos
                if isinstance(hyperparameters, dict):
                    hyperparameters['Chronos'] = {'model_path': chronos_preset}
                    logging.info(f"Добавлена Chronos модель {chronos_preset} к существующим моделям")
                else:
                    # Если hyperparameters не словарь (возможно строка "default"), переопределяем его
                    hyperparameters = {'Chronos': {'model_path': chronos_preset}}
                    logging.info(f"Используется только модель Chronos ({chronos_preset})")
        
        # Логируем финальные параметры
        logging.info(f"Финальное значение hyperparameters: {hyperparameters}")
        logging.info(f"Используемый preset: {preset_to_use}")
        
        # Определяем путь для сохранения модели
        model_name = f"autogluon_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        model_path = os.path.join(TIMESERIES_MODELS_DIR, model_name)
        
        # Обучаем модель
        with st.spinner(f"Обучение модели (ограничение времени: {time_limit} сек)..."):
            # Готовим параметры для вызова train_model
            train_params = {
                "train_data": tsdf,
                "prediction_length": horizon,
                "model_path": model_path,
                "time_limit": time_limit,
                "eval_metric": short_metric,
                "hyperparameters": hyperparameters,
                "preset": preset_to_use
            }
            
            # Явно передаем частоту в train_model, так как она требуется для TimeSeriesPredictor
            if tsdf.freq is None:
                # Если не удалось определить частоту, устанавливаем дефолтное значение
                # и явно очищаем от русского описания
                clean_freq = freq
                if " " in clean_freq:
                    clean_freq = clean_freq.split(" ")[0]
                if "(" in clean_freq:
                    clean_freq = clean_freq.split("(")[0].strip()
                    
                train_params["freq"] = clean_freq  # Используем очищенную частоту
                logging.warning(f"Частота данных не определена, используем '{clean_freq}' по умолчанию")
            else:
                # Если частота уже определена в TimeSeriesDataFrame, используем ее
                train_params["freq"] = tsdf.freq
            
            # Изменяем настройку гиперпараметров для использования всех моделей
            if preset_to_use in ["high_quality", "best_quality", "medium_quality", "good_quality", "fast_training"]:
                # Если используем preset, устанавливаем hyperparameters="default"
                train_params["hyperparameters"] = "default"
                logging.info(f"Используем preset '{preset_to_use}' с hyperparameters='default' для обучения всех подходящих моделей")
            elif models and "all" in models:
                # Если запрошены все модели без пресета, используем hyperparameters="default"
                train_params["hyperparameters"] = "default"
                logging.info("Используем hyperparameters='default' для активации всех доступных моделей AutoGluon TimeSeries")
            
            # Обучаем модель
            model_path, predictor = train_model(**train_params)
            
            # Выполняем прогнозирование на основе обученной модели
            with st.spinner("Выполняем прогнозирование..."):
                try:
                    # Создаем тестовые данные (последние N точек)
                    train_data_split, test_data = tsdf.train_test_split(prediction_length=horizon)
                    
                    # Выполняем прогнозирование
                    predictions = forecast(predictor, train_data_split)
                    
                    # Преобразуем результаты прогноза в DataFrame для отображения
                    forecast_df = convert_predictions_to_dataframe(predictions)
                    
                    # Получаем данные о весах ансамбля, если доступны
                    ensemble_metrics = get_model_performance(predictor)
                    if "ensemble_weights" in ensemble_metrics:
                        ensemble_weights = ensemble_metrics["ensemble_weights"]
                        ensemble_df = pd.DataFrame({
                            "model": list(ensemble_weights.keys()),
                            "weight": list(ensemble_weights.values())
                        })
                    else:
                        ensemble_df = pd.DataFrame(columns=["model", "weight"])
                    
                    # Оценка модели на тестовых данных
                    if test_data is not None:
                        test_metrics = predictor.evaluate(test_data)
                        test_df = pd.DataFrame({
                            "metric": list(test_metrics.keys()), 
                            "value": list(test_metrics.values())
                        })
                    else:
                        test_df = pd.DataFrame(columns=["metric", "value"])
                        
                    # Отображаем результаты прогнозирования
                    st.subheader("Результаты прогнозирования")
                    st.dataframe(forecast_df.head(20))
                    
                    # Строим график прогноза
                    st.subheader("График прогноза")
                    try:
                        # Получаем один временной ряд для примера графика
                        sample_item_id = forecast_df["item_id"].iloc[0]
                        sample_forecast = forecast_df[forecast_df["item_id"] == sample_item_id]
                        
                        # Строим график
                        fig = px.line(sample_forecast, x="timestamp", y="target", title=f"Прогноз для {sample_item_id}")
                        st.plotly_chart(fig)
                    except Exception as plot_err:
                        logging.error(f"Ошибка при построении графика: {plot_err}", exc_info=True)
                    
                except Exception as pred_err:
                    logging.error(f"Ошибка при прогнозировании: {pred_err}", exc_info=True)
                    st.error(f"Не удалось выполнить прогнозирование: {pred_err}")
            
            # Получаем метрики модели
            model_summary = extract_model_metrics(predictor)
            
            # Сохраняем модель и метаданные
            metadata = {
            "model_path": model_path,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "prediction_length": horizon,
                "time_limit": time_limit,
                "eval_metric": eval_metric,
                "data_shape": df_train.shape,
                "num_time_series": len(tsdf.item_ids),
                "data_frequency": str(tsdf.freq),
                "metrics": model_summary
            }
            
            save_model_metadata(model_name, metadata)
            
            # Выводим лидерборд моделей
            if hasattr(predictor, 'leaderboard') and callable(predictor.leaderboard):
                st.subheader("Leaderboard моделей")
                leaderboard_df = predictor.leaderboard()
                st.dataframe(leaderboard_df)
                
                # Сохраняем результаты в Excel
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_file = f"reports/training_leaderboard_{model_name}_{timestamp}.xlsx"
                os.makedirs(os.path.dirname(excel_file), exist_ok=True)
                
                # Создаем Excel-отчет с результатами обучения
                with st.spinner("Сохранение результатов обучения в Excel..."):
                    try:
                        # Запись данных в Excel
                        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                            # Сохраняем лидерборд
                            leaderboard_df.to_excel(writer, sheet_name='Leaderboard', index=False)
                            
                            # Проверяем наличие переменных перед сохранением
                            if 'forecast_df' in locals() and not forecast_df.empty:
                                forecast_df.to_excel(writer, sheet_name='Forecast', index=False)
                            
                            if 'ensemble_df' in locals() and not ensemble_df.empty:
                                ensemble_df.to_excel(writer, sheet_name='Ensemble', index=False)
                            
                            if 'test_df' in locals() and not test_df.empty:
                                test_df.to_excel(writer, sheet_name='Test Performance', index=False)
                                
                        logging.info(f"Результаты обучения сохранены в Excel: {excel_file}")
                        
                        # Восстановить кнопку скачивания Excel файла
                        try:
                            with open(excel_file, "rb") as f:
                                st.download_button(
                                    label=f"Скачать отчет Excel с результатами обучения",
                                    data=f,
                                    file_name=os.path.basename(excel_file),
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key="download_training_report"
                                )
                        except Exception as download_err:
                            logging.error(f"Ошибка при создании кнопки скачивания: {download_err}", exc_info=True)
                    except Exception as excel_err:
                        logging.error(f"Ошибка при сохранении в Excel: {excel_err}", exc_info=True)
                        st.warning(f"Не удалось сохранить результаты в Excel: {excel_err}")
            
            st.success(f"Модель {model_name} успешно обучена и сохранена!")
            
            # Показываем метрики модели
            st.subheader("Информация об обученной модели:")
            
            # Если есть таблица лидеров, показываем её
            if "leaderboard" in model_summary:
                st.dataframe(model_summary["leaderboard"])
            elif "model_info" in model_summary:
                # Показываем базовую информацию о модели
                st.write("### Основная информация о модели")
                info = model_summary["model_info"]
                for key, value in info.items():
                    st.write(f"**{key}**: {value}")
                
                if "note" in model_summary:
                    st.info(model_summary["note"])
            
            # Если есть информация о производительности, показываем её
            if "performance" in model_summary:
                st.write("### Общая производительность")
                for metric, value in model_summary["performance"].items():
                    st.metric(label=metric, value=f"{value:.4f}")
            
            # Сохраняем модель в сессию для последующего использования
            st.session_state["predictor"] = predictor
            st.session_state["model_name"] = model_name
            st.session_state["prediction_length"] = horizon
            
    except (ValueError, KeyError, TypeError) as e:
        logger.error("Ошибка при обучении модели: %s", str(e))
        st.error(f"Ошибка при обучении модели: {str(e)}")
        return None
    except Exception as e:
        logger.error("Неожиданная ошибка при обучении модели: %s", str(e))
        st.error(f"Неожиданная ошибка при обучении модели: {str(e)}")
        return None

# Основной раздел приложения
def main():
    # Заголовок страницы
    st.title("Обучение моделей для прогнозирования временных рядов")
    
    # Загрузка данных
    with st.expander("Загрузка данных", expanded=True):
        uploaded_file = st.file_uploader("Загрузите CSV файл с временными рядами", type=["csv"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"Файл {uploaded_file.name} успешно загружен.")
                
                # Переименование столбцов, если это необходимо
                if st.checkbox("Переименовать столбцы?"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        timestamp_col = st.selectbox("Выберите столбец с временными метками:", df.columns)
                    with col2:
                        id_col = st.selectbox("Выберите столбец с идентификаторами рядов:", df.columns)
                    with col3:
                        target_col = st.selectbox("Выберите столбец с целевой переменной:", df.columns)
                    
                    # Переименовываем столбцы
                    if st.button("Применить переименование столбцов"):
                        df = df.rename(columns={
                            timestamp_col: "timestamp",
                            id_col: "item_id",
                            target_col: "target"
                        })
                        st.success("Столбцы успешно переименованы")
                
                # Отображаем информацию о данных
                show_dataframe_info(df)
                
                # Проверка данных на валидность
                validation_results = validate_forecasting_data(
                    df, 
                    timestamp_col="timestamp", 
                    id_col="item_id", 
                    target_col="target"
                )
                
                # Отображаем результаты валидации
                display_validation_results(validation_results)
                
                if validation_results["valid"]:
                    st.success("Данные проверены и корректны для обучения модели.")
                else:
                    st.error(f"Ошибка в данных: {validation_results['error']}")
                    st.stop()
                
            except Exception as e:
                st.error(f"Ошибка при загрузке файла: {str(e)}")
                logger.error(f"Ошибка при загрузке файла: {str(e)}", exc_info=True)
                df = None
        else:
            st.info("Пожалуйста, загрузите файл с данными.")
            df = None
            st.stop()
    
    # Если данные загружены, отображаем параметры обучения и запускаем обучение
    if df is not None and not df.empty:
        # Получение параметров обучения
        training_params = display_training_parameters()
        
        # Кнопка для запуска обучения
        if st.button("Начать обучение модели"):
            with st.spinner("Обучение модели, пожалуйста подождите..."):
                try:
                    # Создаем TimeSeriesDataFrame
                    logger.info("Создание TimeSeriesDataFrame из набора данных размером %s", df.shape)
                    
                    # Определяем частоту для передачи в make_timeseries_dataframe
                    freq_for_df = training_params.get("freq")
                    
                    tsdf = make_timeseries_dataframe(
                        df=df,
                        freq=freq_for_df,
                        id_column=training_params.get("id_column"),
                        timestamp_column=training_params.get("timestamp_column"),
                        target_column=training_params.get("target_column")
                    )
                    
                    # Настраиваем гиперпараметры для обучения
                    hyperparameters = {}  # По умолчанию пустой словарь

                    if training_params["selected_models"]:
                        # Проверяем, есть ли "all" или "* (все)" в списке моделей
                        if "* (все)" in training_params["selected_models"] or "all" in training_params["selected_models"]:
                            # Используем "default" для включения всех доступных моделей
                            hyperparameters = "default"
                            logging.info("Выбраны все модели (* (все)), используем hyperparameters='default'")
                        else:
                            # Если выбраны конкретные модели
                            valid_models = [
                                'DeepAR', 'ARIMA', 'AutoARIMA', 'AutoETS', 'ETS', 'Theta', 
                                'DirectTabular', 'RecursiveTabular', 'NPTS', 'PatchTST', 
                                'DLinear', 'TiDE', 'TemporalFusionTransformer', 'Naive', 
                                'SeasonalNaive', 'Average', 'SeasonalAverage', 'Chronos'
                            ]
                            
                            # Фильтруем только действительные модели
                            valid_selected_models = [model for model in training_params["selected_models"] if model in valid_models]
                            
                            if valid_selected_models:
                                # Используем только указанные валидные модели
                                hyperparameters = {model: {} for model in valid_selected_models}
                                logging.info("Выбраны конкретные модели для обучения: %s", list(hyperparameters.keys()))
                            else:
                                # Если нет действительных моделей в выборе, используем "default"
                                hyperparameters = "default"
                                logging.warning("Нет действительных моделей в выборе, используем hyperparameters='default'")
                    else:
                        # Если список моделей пуст, используем "default"
                        hyperparameters = "default"
                        logging.info("Список моделей пуст, используем hyperparameters='default'")
                    
                    # Готовим параметры для вызова train_model
                    train_params = {
                        "train_data": tsdf,
                        "prediction_length": training_params["prediction_length"],
                        "model_path": os.path.join(TIMESERIES_MODELS_DIR, training_params["model_name"]),
                        "time_limit": training_params["time_limit"],
                        "eval_metric": training_params["eval_metric"],
                        "hyperparameters": hyperparameters,
                        "preset": training_params["preset"]
                    }
                    
                    # Настройка пресета
                    preset_to_use = "medium_quality" if training_params["time_limit"] > 600 else "fast_training"
                    
                    # Обрабатываем chronos модели, если включены
                    if training_params["use_gpu"] and training_params["preset"] == "chronos":
                        # Используем переданную модель Chronos или bolt_small по умолчанию
                        chronos_preset = training_params["preset"] if training_params["preset"] in ["bolt_tiny", "bolt_mini", "bolt_small", "bolt_base",
                                                                                                  "chronos_tiny", "chronos_mini", "chronos_small", 
                                                                                                  "chronos_base", "chronos_large", "chronos"] else "bolt_small"
                        preset_to_use = chronos_preset
                        logging.info("Используем Chronos модель: %s", chronos_preset)
                        
                        # Важно! Если указаны другие модели, нужно добавить их вместе с Chronos
                        if training_params["selected_models"] and training_params["selected_models"] != ["Chronos"]:
                            # Добавляем выбранную Chronos модель в hyperparameters
                            if not hyperparameters:
                                hyperparameters = {}
                            hyperparameters['Chronos'] = {'model_path': chronos_preset}
                            logging.info("Добавляем Chronos модель к другим выбранным моделям. Всего моделей: %d", len(hyperparameters))
                        else:
                            # Если выбрана только Chronos, то настраиваем preset
                            hyperparameters = {'Chronos': {'model_path': chronos_preset}}
                            logging.info("Используем только Chronos модель с preset %s", chronos_preset)
                    
                    # Обучаем модель
                    logger.info("Запуск обучения модели с параметрами: %s", training_params)
                    
                    # Вызываем функцию обучения с распакованными параметрами
                    model_path, predictor = train_model(**train_params)
                    
                    # Выполняем прогнозирование на основе обученной модели
                    with st.spinner("Выполняем прогнозирование..."):
                        try:
                            # Создаем тестовые данные (последние N точек)
                            train_data_split, test_data = tsdf.train_test_split(prediction_length=training_params["prediction_length"])
                            
                            # Выполняем прогнозирование
                            predictions = forecast(predictor, train_data_split)
                            
                            # Преобразуем результаты прогноза в DataFrame для отображения
                            forecast_df = convert_predictions_to_dataframe(predictions)
                            
                            # Получаем данные о весах ансамбля, если доступны
                            ensemble_metrics = get_model_performance(predictor)
                            if "ensemble_weights" in ensemble_metrics:
                                ensemble_weights = ensemble_metrics["ensemble_weights"]
                                ensemble_df = pd.DataFrame({
                                    "model": list(ensemble_weights.keys()),
                                    "weight": list(ensemble_weights.values())
                                })
                            else:
                                ensemble_df = pd.DataFrame(columns=["model", "weight"])
                            
                            # Оценка модели на тестовых данных
                            if test_data is not None:
                                test_metrics = predictor.evaluate(test_data)
                                test_df = pd.DataFrame({
                                    "metric": list(test_metrics.keys()), 
                                    "value": list(test_metrics.values())
                                })
                            else:
                                test_df = pd.DataFrame(columns=["metric", "value"])
                                
                            # Отображаем результаты прогнозирования
                            st.subheader("Результаты прогнозирования")
                            st.dataframe(forecast_df.head(20))
                            
                            # Строим график прогноза
                            st.subheader("График прогноза")
                            try:
                                # Получаем один временной ряд для примера графика
                                sample_item_id = forecast_df["item_id"].iloc[0]
                                sample_forecast = forecast_df[forecast_df["item_id"] == sample_item_id]
                                
                                # Строим график
                                fig = px.line(sample_forecast, x="timestamp", y="target", title=f"Прогноз для {sample_item_id}")
                                st.plotly_chart(fig)
                            except Exception as plot_err:
                                logging.error(f"Ошибка при построении графика: {plot_err}", exc_info=True)
                            
                        except Exception as pred_err:
                            logging.error(f"Ошибка при прогнозировании: {pred_err}", exc_info=True)
                            st.error(f"Не удалось выполнить прогнозирование: {pred_err}")
                    
                    # Получаем метрики модели
                    model_summary = extract_model_metrics(predictor)
                    
                    # Сохраняем модель и метаданные
                    metadata = {
                        "model_path": model_path,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "prediction_length": training_params["prediction_length"],
                        "time_limit": training_params["time_limit"],
                        "eval_metric": training_params["eval_metric"],
                        "data_shape": df.shape,
                        "num_time_series": len(tsdf.item_ids),
                        "data_frequency": str(tsdf.freq),
                        "metrics": model_summary
                    }
                    
                    save_model_metadata(training_params["model_name"], metadata)
                    
                    # Выводим лидерборд моделей
                    if hasattr(predictor, 'leaderboard') and callable(predictor.leaderboard):
                        st.subheader("Leaderboard моделей")
                        leaderboard_df = predictor.leaderboard()
                        st.dataframe(leaderboard_df)
                        
                        # Сохраняем результаты в Excel
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        excel_file = f"reports/training_leaderboard_{training_params['model_name']}_{timestamp}.xlsx"
                        os.makedirs(os.path.dirname(excel_file), exist_ok=True)
                        
                        # Создаем Excel-отчет с результатами обучения
                        with st.spinner("Сохранение результатов обучения в Excel..."):
                            try:
                                # Запись данных в Excel
                                with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                                    # Сохраняем лидерборд
                                    leaderboard_df.to_excel(writer, sheet_name='Leaderboard', index=False)
                                    
                                    # Проверяем наличие переменных перед сохранением
                                    if 'forecast_df' in locals() and not forecast_df.empty:
                                        forecast_df.to_excel(writer, sheet_name='Forecast', index=False)
                                    
                                    if 'ensemble_df' in locals() and not ensemble_df.empty:
                                        ensemble_df.to_excel(writer, sheet_name='Ensemble', index=False)
                                    
                                    if 'test_df' in locals() and not test_df.empty:
                                        test_df.to_excel(writer, sheet_name='Test Performance', index=False)
                                    
                                logging.info(f"Результаты обучения сохранены в Excel: {excel_file}")
                                
                                # Восстановить кнопку скачивания Excel файла
                                try:
                                    with open(excel_file, "rb") as f:
                                        st.download_button(
                                            label=f"Скачать отчет Excel с результатами обучения",
                                            data=f,
                                            file_name=os.path.basename(excel_file),
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            key="download_training_report"
                                        )
                                except Exception as download_err:
                                    logging.error(f"Ошибка при создании кнопки скачивания: {download_err}", exc_info=True)
                            except Exception as excel_err:
                                logging.error(f"Ошибка при сохранении в Excel: {excel_err}", exc_info=True)
                                st.warning(f"Не удалось сохранить результаты в Excel: {excel_err}")
                        
                        st.success(f"Модель {training_params['model_name']} успешно обучена и сохранена!")
                        
                        # Показываем метрики модели
                        st.subheader("Информация об обученной модели:")
                        
                        # Если есть таблица лидеров, показываем её
                        if "leaderboard" in model_summary:
                            st.dataframe(model_summary["leaderboard"])
                        elif "model_info" in model_summary:
                            # Показываем базовую информацию о модели
                            st.write("### Основная информация о модели")
                            info = model_summary["model_info"]
                            for key, value in info.items():
                                st.write(f"**{key}**: {value}")
                            
                            if "note" in model_summary:
                                st.info(model_summary["note"])
                        
                        # Если есть информация о производительности, показываем её
                        if "performance" in model_summary:
                            st.write("### Общая производительность")
                            for metric, value in model_summary["performance"].items():
                                st.metric(label=metric, value=f"{value:.4f}")
                        
                        # Предлагаем перейти на страницу прогнозирования
                        st.info("Теперь вы можете перейти на вкладку 'Прогнозирование' для использования модели.")
                        
                except (ValueError, KeyError, TypeError) as e:
                    logger.error("Ошибка при обучении модели: %s", str(e))
                    st.error(f"Ошибка при обучении модели: {str(e)}")
                    return None
                except Exception as e:
                    logger.error("Неожиданная ошибка при обучении модели: %s", str(e))
                    st.error(f"Неожиданная ошибка при обучении модели: {str(e)}")
                    return None

if __name__ == "__main__":
    try:
        # Проверяем, что файл был загружен
        if "df_train" not in st.session_state or st.session_state.get("df_train") is None:
            st.warning("Необходимо сначала загрузить данные. Пожалуйста, вернитесь на вкладку 'Загрузка данных'.")
        else:
            # Получаем датафрейм из состояния сессии
            df_train = st.session_state.df_train
            
            # Запускаем процесс обучения
            run_training(df_train)
    
    except ValueError as ve:
        st.error(f"Ошибка валидации данных: {ve}")
        logging.error("Ошибка валидации данных: %s", ve)
    except TypeError as te:
        st.error(f"Ошибка типа данных: {te}")
        logging.error("Ошибка типа данных: %s", te)
    except RuntimeError as re:
        st.error(f"Ошибка выполнения: {re}")
        logging.error("Ошибка выполнения: %s", re)
    except KeyError as ke:
        st.error(f"Ошибка доступа к данным: {ke}")
        logging.error("Ошибка доступа к данным: %s", ke)
    except Exception as e:
        st.error(f"Произошла неожиданная ошибка: {e}")
        logging.error("Произошла неожиданная ошибка: %s", e, exc_info=True)