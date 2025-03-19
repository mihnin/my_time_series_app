# app_training.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import logging
import os
from datetime import datetime
from pathlib import Path

try:
    from app_ui import display_error_message
except ImportError:
    # Если не удалось импортировать, создадим простую функцию
    def display_error_message(error_text, title="Ошибка"):
        st.error(f"{title}: {error_text}")

from src.utils.config import (
    TIMESERIES_MODELS_DIR, MODEL_METADATA_FILE, LOGS_DIR,
    DEFAULT_CHUNK_SIZE, DEFAULT_PREDICTION_LENGTH, DEFAULT_TIME_LIMIT,
    MAX_VISUALIZE_POINTS
)
from src.models.forecasting import (
    make_timeseries_dataframe, train_model, extract_model_metrics
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
    metadata[model_name] = info_dict
    
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
            model_types = ["DeepAR", "Chronos", "ETS", "Prophet", "Transformer", "* (все)"]
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
        # Загружаем конфигурацию с метриками
        from app_ui import METRICS_DICT, FREQ_REVERSE_MAPPING
        
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
        
        # Конвертируем отображаемое значение частоты в значение для AutoGluon
        base_freq = freq
        if freq in FREQ_REVERSE_MAPPING:
            base_freq = FREQ_REVERSE_MAPPING[freq]
            logging.info(f"Преобразована частота из {freq} в {base_freq}")
        else:
            logging.info(f"Используем частоту {base_freq} без преобразования")
        
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
                freq=base_freq
            )
            
            # Проверяем, что частота корректно установлена
            logging.info(f"TimeSeriesDataFrame создан с частотой {getattr(tsdf, 'freq', 'не определена')}")
            logging.info(f"Количество рядов в TimeSeriesDataFrame: {len(tsdf)}")
            if len(tsdf) == 0:
                raise ValueError("TimeSeriesDataFrame не содержит данных")
                
            # Выводим идентификаторы рядов
            item_ids = tsdf.item_ids
            logging.info(f"Идентификаторы рядов: {item_ids[:5]}{'...' if len(item_ids) > 5 else ''}")
            
            st.success(f"TimeSeriesDataFrame успешно создан, содержит {len(tsdf)} рядов")
        
        # Настройка гиперпараметров и модели
        preset_to_use = "medium_quality" if time_limit > 600 else "fast_training"
        hyperparameters = {}  # По умолчанию пустой словарь

        if models:
            # Преобразуем строку моделей в список, если нужно
            if isinstance(models, str):
                if models == "all":
                    # Случай "all" - не указываем модели, используем пресет
                    models = []
                    logging.info("Выбраны все модели (all), будет использоваться пресет")
                else:
                    models = [model.strip() for model in models.split(',')]
                    
            logging.info(f"Исходный список выбранных моделей: {models}")
            
            # Проверяем наличие специального значения "* (все)"
            if models and "* (все)" in models:
                # Если выбрано "все модели", не указываем конкретные модели
                models = []
                logging.info("Выбраны все модели (* (все)), будет использоваться пресет")
                
            # Проверяем, есть ли в списке действительные модели AutoGluon
            if models:
                valid_models = [
                    'DeepAR', 'ARIMA', 'AutoARIMA', 'AutoETS', 'ETS', 'Theta', 
                    'DirectTabular', 'RecursiveTabular', 'NPTS', 'PatchTST', 
                    'DLinear', 'TiDE', 'TemporalFusionTransformer', 'Naive', 
                    'SeasonalNaive', 'Average', 'SeasonalAverage', 'Chronos'
                ]
                
                # Фильтруем только действительные модели
                valid_selected_models = [model for model in models if model in valid_models]
                
                if valid_selected_models:
                    # Используем только указанные валидные модели
                    hyperparameters = {model: {} for model in valid_selected_models}
                    logging.info(f"Выбраны конкретные модели для обучения: {list(hyperparameters.keys())}")
                else:
                    # Если нет действительных моделей в выборе, используем DeepAR как дефолтную
                    hyperparameters = {"DeepAR": {}}
                    logging.warning("Нет действительных моделей в выборе, используем DeepAR как дефолтную модель")
            else:
                # Если список моделей пуст, передаем пустой hyperparameters
                # forecasting.train_model() обработает этот случай
                hyperparameters = {}
                logging.info("Список моделей пуст, для предотвращения ошибок будет использоваться модель по умолчанию")
        
        # Обрабатываем chronos модели, если включены
        if use_chronos and chronos_model:
            # Используем переданную модель Chronos или bolt_small по умолчанию
            chronos_preset = chronos_model if chronos_model in ["bolt_tiny", "bolt_mini", "bolt_small", "bolt_base",
                                                              "chronos_tiny", "chronos_mini", "chronos_small", 
                                                              "chronos_base", "chronos_large", "chronos"] else "bolt_small"
            preset_to_use = chronos_preset
            logging.info(f"Используем Chronos модель: {chronos_preset}")
            
        # Определяем путь для сохранения модели
        model_name = f"autogluon_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        model_path = os.path.join(TIMESERIES_MODELS_DIR, model_name)
        
        # Обучаем модель
        with st.spinner(f"Обучение модели (ограничение времени: {time_limit} сек)..."):
            model_path, predictor = train_model(
                train_data=tsdf,
                prediction_length=horizon,
                model_path=model_path,
                time_limit=time_limit,
                eval_metric=short_metric,
                hyperparameters=hyperparameters,
                preset=preset_to_use,
                freq=base_freq
            )
            
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
            
            st.success(f"Модель {model_name} успешно обучена и сохранена!")
            
            # Показываем метрики модели
            st.subheader("Метрики обученной модели:")
            
            if "leaderboard" in model_summary:
                st.dataframe(model_summary["leaderboard"])
            
            if "performance" in model_summary:
                st.write("### Общая производительность")
                for metric, value in model_summary["performance"].items():
                    st.metric(label=metric, value=f"{value:.4f}")
            
            # Сохраняем модель в сессию для последующего использования
            st.session_state["predictor"] = predictor
            st.session_state["model_name"] = model_name
            st.session_state["prediction_length"] = horizon
            
    except Exception as e:
        if "display_error_message" in globals():
            display_error_message(str(e), title="Ошибка при обучении модели")
        else:
            try:
                from app_ui import display_error_message
                display_error_message(str(e), title="Ошибка при обучении модели")
            except:
                st.error(f"Ошибка при обучении модели: {str(e)}")
        logger.error(f"Ошибка при обучении модели: {str(e)}", exc_info=True)
        # Не поднимаем ошибку повторно, так как это может вызвать проблемы в Streamlit

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
                    logger.info(f"Создание TimeSeriesDataFrame из набора данных размером {df.shape}")
                    tsdf = make_timeseries_dataframe(
                        df=df,
                        freq=training_params["freq"],
                        id_column=training_params["id_column"],
                        timestamp_column=training_params["timestamp_column"],
                        target_column=training_params["target_column"]
                    )
                    logger.info(f"TimeSeriesDataFrame успешно создан, содержит {len(tsdf)} рядов")
                    
                    # Настраиваем гиперпараметры для обучения
                    hyperparameters = {}  # По умолчанию пустой словарь

                    if training_params["selected_models"]:
                        # Преобразуем строку моделей в список, если нужно
                        if isinstance(training_params["selected_models"], str):
                            if training_params["selected_models"] == "all":
                                # Случай "all" - не указываем модели, используем пресет
                                training_params["selected_models"] = []
                                logging.info("Выбраны все модели (all), будет использоваться пресет")
                            else:
                                training_params["selected_models"] = [model.strip() for model in training_params["selected_models"].split(',')]
                                
                        logging.info(f"Исходный список выбранных моделей: {training_params['selected_models']}")
                        
                        # Проверяем наличие специального значения "* (все)"
                        if training_params["selected_models"] and "* (все)" in training_params["selected_models"]:
                            # Если выбрано "все модели", не указываем конкретные модели
                            training_params["selected_models"] = []
                            logging.info("Выбраны все модели (* (все)), будет использоваться пресет")
                            
                        # Проверяем, есть ли в списке действительные модели AutoGluon
                        if training_params["selected_models"]:
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
                                logging.info(f"Выбраны конкретные модели для обучения: {list(hyperparameters.keys())}")
                            else:
                                # Если нет действительных моделей в выборе, используем DeepAR как дефолтную
                                hyperparameters = {"DeepAR": {}}
                                logging.warning("Нет действительных моделей в выборе, используем DeepAR как дефолтную модель")
                        else:
                            # Если список моделей пуст, передаем пустой hyperparameters
                            # forecasting.train_model() обработает этот случай
                            hyperparameters = {}
                            logging.info("Список моделей пуст, для предотвращения ошибок будет использоваться модель по умолчанию")
                    
                    # Настройка пресета
                    preset_to_use = "medium_quality" if training_params["time_limit"] > 600 else "fast_training"
                    
                    # Обрабатываем chronos модели, если включены
                    if training_params["use_gpu"] and training_params["preset"] == "chronos":
                        # Используем переданную модель Chronos или bolt_small по умолчанию
                        chronos_preset = training_params["preset"] if training_params["preset"] in ["bolt_tiny", "bolt_mini", "bolt_small", "bolt_base",
                                                                                                  "chronos_tiny", "chronos_mini", "chronos_small", 
                                                                                                  "chronos_base", "chronos_large", "chronos"] else "bolt_small"
                        preset_to_use = chronos_preset
                        logging.info(f"Используем Chronos модель: {chronos_preset}")
                    
                    # Обучаем модель
                    logger.info(f"Запуск обучения модели с параметрами: {training_params}")
                    model_path, predictor = train_model(
                        train_data=tsdf,
                        prediction_length=training_params["prediction_length"],
                        model_path=os.path.join(TIMESERIES_MODELS_DIR, training_params["model_name"]),
                        time_limit=training_params["time_limit"],
                        eval_metric=training_params["eval_metric"],
                        hyperparameters=hyperparameters,
                        preset=preset_to_use,
                        freq=training_params["freq"]
                    )
                    
                    # Получаем метрики модели
                    model_summary = extract_model_metrics(predictor)
                    
                    # Сохраняем метаданные модели
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
                    
                    # Отображаем результат обучения
                    st.success(f"Модель {training_params['model_name']} успешно обучена и сохранена!")
                    
                    # Показываем метрики модели
                    st.subheader("Метрики обученной модели:")
                    
                    if "leaderboard" in model_summary:
                        st.dataframe(model_summary["leaderboard"])
                    
                    if "performance" in model_summary:
                        st.json(model_summary["performance"])
                    
                    # Предлагаем перейти на страницу прогнозирования
                    st.info("Теперь вы можете перейти на вкладку 'Прогнозирование' для использования модели.")
                    
                except Exception as e:
                    if "display_error_message" in globals():
                        display_error_message(str(e), title="Ошибка при обучении модели")
                    else:
                        try:
                            from app_ui import display_error_message
                            display_error_message(str(e), title="Ошибка при обучении модели")
                        except:
                            st.error(f"Ошибка при обучении модели: {str(e)}")
                    logger.error(f"Ошибка при обучении модели: {str(e)}", exc_info=True)
                    # Не поднимаем ошибку повторно, так как это может вызвать проблемы в Streamlit

if __name__ == "__main__":
    run_training()