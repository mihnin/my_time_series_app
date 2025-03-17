# src/utils/exporter.py
import io
import pandas as pd
import logging
import os
from pathlib import Path

# Пытаемся импортировать openpyxl.styles, если не удается, используем заглушку
try:
    from openpyxl.styles import PatternFill
    OPENPYXL_AVAILABLE = True
except ImportError:
    logging.warning("openpyxl.styles не установлен, подсветка ячеек в Excel не будет работать")
    # Создаем заглушку для PatternFill
    class PatternFill:
        def __init__(self, start_color=None, end_color=None, fill_type=None):
            self.start_color = start_color
            self.end_color = end_color
            self.fill_type = fill_type
    OPENPYXL_AVAILABLE = False

# Словарь соответствия названий моделей и их локальных путей
CHRONOS_MODELS_MAPPING = {
    "bolt_tiny": "chronos-bolt-tiny",
    "bolt_small": "chronos-bolt-small", 
    "bolt_base": "chronos-bolt-base",
    "autogluon/chronos-bolt-tiny": "chronos-bolt-tiny",
    "autogluon/chronos-bolt-small": "chronos-bolt-small",
    "autogluon/chronos-bolt-base": "chronos-bolt-base"
}

def get_local_model_path(model_name):
    """
    Возвращает локальный путь к модели Chronos, если она доступна
    
    Аргументы:
        model_name (str): Имя модели
    
    Возвращает:
        str: Абсолютный путь к локальной модели или исходное имя модели
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    chronos_dir = os.path.join(base_dir, "autogluon")
    
    if (model_name in CHRONOS_MODELS_MAPPING):
        model_dir = os.path.join(chronos_dir, CHRONOS_MODELS_MAPPING[model_name])
        if os.path.exists(model_dir):
            logging.info(f"ВАЖНО: Используется локальная модель Chronos из папки: {model_dir}")
            # Проверяем наличие модельного файла
            model_file = os.path.join(model_dir, "model.safetensors")
            if os.path.exists(model_file):
                model_size_mb = round(os.path.getsize(model_file) / (1024 * 1024), 2)
                logging.info(f"Размер файла модели: {model_size_mb} МБ")
            return model_dir
    
    logging.info(f"Локальная модель не найдена для {model_name}, будет использован Hugging Face")
    return model_name

def generate_excel_buffer(result):
    """
    Формирует Excel-файл в памяти с результатами прогнозирования или обучения
    
    Аргументы:
        result (dict): Результат прогнозирования/обучения, содержащий различные данные:
            - forecasts: словарь прогнозов для разных целевых переменных
            - leaderboard: таблица с результатами обучения моделей
            - ensemble_info: информация о весах моделей в ансамбле
            - module_error: информация об ошибках модулей
            - summary_data: сводная информация о результатах
    
    Возвращает:
        BytesIO: Объект BytesIO с Excel-файлом или None в случае ошибки
    """
    # Инициализируем буфер для Excel
    excel_buffer = io.BytesIO()
    
    # Флаг успешной записи в Excel
    excel_written = False
    
    try:
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            # Проверяем успешность результата
            if not result.get('success', False):
                # Создаем лист с ошибкой
                pd.DataFrame([{"Ошибка": result.get('error', 'Неизвестная ошибка')}]).to_excel(
                    writer, sheet_name="Ошибка", index=False)
                excel_written = True
                return excel_buffer
            
            # Счетчик созданных листов
            sheets_created = 0
            
            # ===== 1. Обработка прогнозов =====
            if 'forecasts' in result and isinstance(result['forecasts'], dict):
                sheet_idx = 0  # Индекс для именования листов при длинных именах
                
                for target_col, forecast_data in result['forecasts'].items():
                    predictions = forecast_data.get('predictions')
                    if predictions is not None and not predictions.empty:
                        sheet_name = f"Прогноз_{target_col}"
                        if len(sheet_name) > 31:  # Ограничение Excel на длину имени листа
                            sheet_name = f"Прогноз_{sheet_idx}"
                            sheet_idx += 1
                        
                        # Сбрасываем индекс для экспорта в Excel
                        predictions.reset_index().to_excel(writer, sheet_name=sheet_name, index=False)
                        sheets_created += 1
                        excel_written = True
                        logging.info(f"Лист с прогнозом для {target_col} успешно создан")
            
            # ===== 2. Обработка сводных данных =====
            if 'summary_data' in result and isinstance(result['summary_data'], dict):
                # Преобразуем сводные данные в DataFrame для Excel
                summary_data = []
                
                for metric_key, metric_value in result['summary_data'].items():
                    if isinstance(metric_value, dict):
                        for sub_key, sub_value in metric_value.items():
                            summary_data.append({"Метрика": f"{metric_key}: {sub_key}", "Значение": sub_value})
                    else:
                        summary_data.append({"Метрика": metric_key, "Значение": metric_value})
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name="Сводка", index=False)
                    sheets_created += 1
                    excel_written = True
                    logging.info(f"Лист со сводными данными успешно создан")
            
            # ===== 3. Обработка информации об ошибках модулей =====
            if 'module_error' in result:
                error_msg = result['module_error']
                if isinstance(error_msg, str):
                    pd.DataFrame([{"Сообщение": error_msg}]).to_excel(writer, sheet_name="Ошибки_модулей", index=False)
                    sheets_created += 1
                    excel_written = True
                    logging.info(f"Лист с информацией об ошибках модулей успешно создан")
            
            # ===== 4. Обработка лидерборда =====
            if 'leaderboard' in result and isinstance(result.get('leaderboard'), pd.DataFrame):
                leaderboard = result['leaderboard']
                if not leaderboard.empty:
                    # Округляем числовые значения для лучшего отображения
                    for col in leaderboard.select_dtypes(include=['float']).columns:
                        leaderboard[col] = leaderboard[col].round(6)
                    
                    leaderboard.to_excel(writer, sheet_name="Лидерборд", index=False)
                    sheets_created += 1
                    excel_written = True
                    logging.info(f"Лист с лидербордом успешно создан")
            
            # ===== 5. Обработка ансамблевых весов =====
            ensemble_weights_df = None
            model_details_df = None
            
            # Способ 1: Уже извлеченные веса ансамбля
            if 'ensemble_info' in result:
                ensemble_info = result['ensemble_info']
                if isinstance(ensemble_info, tuple) and len(ensemble_info) == 2:
                    ensemble_weights_df, model_details_df = ensemble_info
                elif isinstance(ensemble_info, dict):
                    if 'weights' in ensemble_info:
                        ensemble_weights_df = ensemble_info['weights']
                    if 'details' in ensemble_info:
                        model_details_df = ensemble_info['details']
            
            # Способ 2: Извлечение весов из предиктора, если доступен
            if ensemble_weights_df is None and 'predictor' in result:
                try:
                    ensemble_weights_df, model_details_df = extract_ensemble_weights(result['predictor'])
                except Exception as e:
                    logging.warning(f"Не удалось извлечь информацию об ансамбле из предиктора: {e}")
            
            # Сохраняем веса ансамбля, если они есть
            if ensemble_weights_df is not None and isinstance(ensemble_weights_df, pd.DataFrame) and not ensemble_weights_df.empty:
                ensemble_weights_df.to_excel(writer, sheet_name="Веса_ансамбля", index=False)
                sheets_created += 1
                excel_written = True
                logging.info(f"Лист с весами ансамбля успешно создан")
            
            # Сохраняем детали моделей, если они есть
            if model_details_df is not None and isinstance(model_details_df, pd.DataFrame) and not model_details_df.empty:
                model_details_df.to_excel(writer, sheet_name="Детали_моделей", index=False)
                sheets_created += 1
                excel_written = True
                logging.info(f"Лист с деталями моделей успешно создан")
            
            # Если не создано ни одного листа, добавляем информационный лист
            if sheets_created == 0:
                pd.DataFrame([{"Информация": "Нет данных для отображения в Excel"}]).to_excel(
                    writer, sheet_name="Информация", index=False)
                excel_written = True
                logging.warning(f"В результатах не найдено данных для экспорта в Excel")
            
            # Дополнительное логирование
            logging.info(f"Excel-файл успешно создан, листов: {sheets_created}")
    
    except Exception as e:
        error_msg = f"Ошибка при создании Excel-файла: {str(e)}"
        logging.error(error_msg)
        
        # Пытаемся создать простой Excel-файл с информацией об ошибке
        try:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                pd.DataFrame([{"Ошибка": error_msg}]).to_excel(writer, sheet_name="Ошибка", index=False)
                excel_written = True
        except Exception as inner_e:
            logging.error(f"Не удалось создать Excel-файл даже с информацией об ошибке: {str(inner_e)}")
            return None
    
    # Проверяем, что хотя бы один лист был успешно создан
    if not excel_written:
        logging.error("Excel-файл не был создан из-за отсутствия данных или ошибок")
        return None
    
    # Возвращаем указатель в начало буфера
    excel_buffer.seek(0)
    return excel_buffer

def extract_ensemble_weights(predictor):
    """
    Извлекает информацию о составе и весах ансамблевой модели
    
    Аргументы:
        predictor: Обученный TimeSeriesPredictor
    
    Возвращает:
        tuple: (weights_df, details_df) или (None, None)
            weights_df: pandas.DataFrame с весами моделей
            details_df: pandas.DataFrame с дополнительной информацией о моделях
    """
    try:
        if not predictor:
            logging.warning("Предиктор не предоставлен для извлечения весов ансамбля")
            return None, None
            
        # Проверяем, является ли лучшая модель ансамблевой
        try:
            # Используем новое property model_best вместо устаревшего метода get_model_best
            best_model_name = predictor.model_best if hasattr(predictor, 'model_best') else predictor.get_model_best()
            logging.info(f"Лучшая модель: {best_model_name}")
            if "Ensemble" not in best_model_name:
                logging.info(f"Лучшая модель не является ансамблевой: {best_model_name}")
                return None, None
        except Exception as e:
            logging.warning(f"Не удалось определить, является ли лучшая модель ансамблевой: {e}")
            # Продолжаем выполнение, так как ансамбль все равно может существовать
            
        # Пробуем получить информацию об ансамбле разными способами
        ensemble_weights = None
        model_details_list = []  # Изменено с model_details на model_details_list для ясности
        
        # Способ 1: Прямой метод get_model_weights() или weights_
        try:
            # Сначала пробуем новый способ получения весов через атрибут weights_
            if hasattr(predictor, 'weights_'):
                ensemble_weights = predictor.weights_
                if isinstance(ensemble_weights, dict):
                    ensemble_weights = pd.DataFrame({
                        'Модель': list(ensemble_weights.keys()),
                        'Вес': list(ensemble_weights.values())
                    })
                logging.info("Веса ансамбля успешно извлечены через атрибут weights_")
            elif hasattr(predictor, 'get_model_weights'):
                ensemble_weights = predictor.get_model_weights()
                logging.info("Веса ансамбля успешно извлечены методом get_model_weights()")
            
            if ensemble_weights is not None:
                logging.info(f"Веса ансамбля успешно извлечены, форма: {ensemble_weights.shape if isinstance(ensemble_weights, pd.DataFrame) else 'dict'}")
        except (AttributeError, Exception) as e:
            logging.warning(f"Не удалось получить веса ансамбля стандартным методом: {e}")
            
        # Способ 2: Через директории и файлы модели
        if ensemble_weights is None:
            try:
                # Получаем путь к директории модели
                if hasattr(predictor, 'path'):
                    model_path = predictor.path
                else:
                    # Пробуем альтернативный способ получения пути к моделям
                    model_path = getattr(predictor, '_learner_path', None)
                    if not model_path:
                        # Пробуем получить путь из _learner объекта, если он есть
                        learner = getattr(predictor, '_learner', None)
                        if learner:
                            model_path = getattr(learner, 'path', None)
                
                if not model_path:
                    logging.warning("Не удалось определить путь к моделям")
                    return None, None
                    
                logging.info(f"Путь к модели: {model_path}")
                
                # Проверяем разные варианты директорий моделей
                models_dirs = [
                    os.path.join(model_path, "models"),
                    model_path,
                    os.path.join(model_path, ".."),
                    os.path.join(model_path, "..", "models")
                ]
                
                models_dir = None
                for dir_path in models_dirs:
                    if os.path.exists(dir_path) and os.path.isdir(dir_path):
                        # Проверяем, есть ли в директории файлы .pkl
                        pkl_files = [f for f in os.listdir(dir_path) if f.endswith('.pkl')]
                        if pkl_files:
                            models_dir = dir_path
                            logging.info(f"Найдена директория с моделями: {models_dir}")
                            break
                
                if not models_dir:
                    logging.warning("Не найдена директория с моделями")
                    return None, None
                
                # Ищем файл ансамблевой модели с более гибким поиском
                ensemble_file = None
                ensemble_patterns = ["Ensemble", "ensemble", "WeightedEnsemble"]
                
                for filename in os.listdir(models_dir):
                    if filename.endswith(".pkl") and any(pattern in filename for pattern in ensemble_patterns):
                        ensemble_file = os.path.join(models_dir, filename)
                        logging.info(f"Найден файл ансамбля: {ensemble_file}")
                        break
                
                if not ensemble_file:
                    # Попробуем поискать в подпапках
                    for root, dirs, files in os.walk(models_dir):
                        for filename in files:
                            if filename.endswith(".pkl") and any(pattern in filename for pattern in ensemble_patterns):
                                ensemble_file = os.path.join(root, filename)
                                logging.info(f"Найден файл ансамбля в подпапке: {ensemble_file}")
                                break
                        if ensemble_file:
                            break
                
                if ensemble_file:
                    import pickle
                    
                    try:
                        with open(ensemble_file, 'rb') as f:
                            ensemble_model = pickle.load(f)
                            logging.info(f"Тип ансамблевой модели: {type(ensemble_model).__name__}")
                            
                            # Получаем веса - проверяем разные атрибуты, которые могут содержать веса
                            weights = None
                            for attr_name in ['weights', '_weights', 'model_weights', 'weights_', 'w_']:
                                if hasattr(ensemble_model, attr_name):
                                    weights = getattr(ensemble_model, attr_name)
                                    logging.info(f"Найдены веса в атрибуте {attr_name}")
                                    break
                            
                            if weights is None:
                                # Еще один подход: попробуем изучить все атрибуты модели
                                for attr_name in dir(ensemble_model):
                                    if 'weight' in attr_name.lower() and not attr_name.startswith('_'):
                                        attr_value = getattr(ensemble_model, attr_name)
                                        if isinstance(attr_value, dict) or isinstance(attr_value, pd.DataFrame):
                                            weights = attr_value
                                            logging.info(f"Найдены веса в атрибуте {attr_name}")
                                            break
                            
                            if weights is not None:
                                if isinstance(weights, dict):
                                    ensemble_weights = pd.DataFrame({
                                        'Модель': list(weights.keys()),
                                        'Вес': list(weights.values())
                                    })
                                    ensemble_weights = ensemble_weights.sort_values('Вес', ascending=False)
                                    logging.info(f"Извлечены веса для {len(weights)} моделей из ансамбля")
                                    
                                    # Собираем детальную информацию о моделях
                                    for model_name in weights.keys():
                                        model_info = {'Название модели': model_name}
                                        
                                        # Более гибкий поиск файла модели
                                        model_file = None
                                        for filename in os.listdir(models_dir):
                                            if filename.endswith(".pkl") and (
                                                filename.startswith(model_name) or 
                                                model_name in filename
                                            ):
                                                model_file = os.path.join(models_dir, filename)
                                                break
                                        
                                        if model_file:
                                            try:
                                                with open(model_file, 'rb') as f:
                                                    model = pickle.load(f)
                                                    
                                                # Получаем параметры модели
                                                if hasattr(model, 'get_params'):
                                                    params = model.get_params()
                                                    model_info.update({
                                                        'Параметры': str(params)
                                                    })
                                                else:
                                                    # Альтернативное получение параметров
                                                    params = {}
                                                    for attr_name in dir(model):
                                                        if not attr_name.startswith('_') and not callable(getattr(model, attr_name)):
                                                            try:
                                                                attr_value = getattr(model, attr_name)
                                                                if isinstance(attr_value, (int, float, str, bool)):
                                                                    params[attr_name] = attr_value
                                                            except:
                                                                pass
                                                    
                                                    if params:
                                                        model_info.update({
                                                            'Параметры': str(params)
                                                        })
                                                
                                                # Получаем метрики модели, если есть
                                                for metric_attr in ['score', 'metric', 'score_val', 'val_score']:
                                                    if hasattr(model, metric_attr):
                                                        model_info['Метрика'] = str(getattr(model, metric_attr))
                                                        break
                                            except Exception as e:
                                                logging.warning(f"Ошибка при получении информации о модели {model_name}: {e}")
                                        else:
                                            logging.warning(f"Не удалось найти файл модели для {model_name}")
                                        
                                        model_details_list.append(model_info)
                                elif isinstance(weights, pd.DataFrame):
                                    ensemble_weights = weights
                                    logging.info(f"Извлечены веса как DataFrame, строк: {len(ensemble_weights)}")
                                else:
                                    logging.warning(f"Веса ансамбля в неожиданном формате: {type(weights)}")
                            else:
                                logging.warning("Не удалось найти атрибут с весами в ансамблевой модели")
                    except Exception as e:
                        logging.warning(f"Ошибка при загрузке и обработке ансамблевой модели: {e}")
                else:
                    logging.warning("Файл ансамблевой модели не найден в директории моделей")
                
            except Exception as e:
                logging.warning(f"Ошибка при получении детальной информации о моделях: {e}")
        
        # Создаем DataFrame с детальной информацией
        details_df = pd.DataFrame(model_details_list) if model_details_list else None
        
        # Логируем результаты
        if ensemble_weights is not None:
            logging.info(f"Успешно извлечены веса ансамбля: {len(ensemble_weights)} моделей")
        else:
            logging.warning("Не удалось извлечь веса ансамбля")
            
        if details_df is not None:
            logging.info(f"Успешно извлечена детальная информация о {len(details_df)} моделях")
        else:
            logging.warning("Не удалось извлечь детальную информацию о моделях")
        
        return ensemble_weights, details_df
        
    except Exception as e:
        logging.warning(f"Не удалось получить информацию о составе ансамбля: {e}")
        return None, None

# Старая функция оставлена для совместимости, но помечена как устаревшая
def generate_excel_buffer_legacy(preds, leaderboard, static_train, ensemble_info_df):
    """
    УСТАРЕВШАЯ ФУНКЦИЯ - используйте generate_excel_buffer(result)
    
    Формирует Excel-файл в памяти с листами:
      - Predictions
      - Leaderboard с подсветкой лучшей модели
      - StaticTrainFeatures
      - WeightedEnsembleInfo
    
    Возвращает объект BytesIO с Excel-файлом.
    """
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        # Лист с предсказаниями
        if preds is not None:
            preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False)
        # Лидерборд с подсветкой лучшей модели
        if leaderboard is not None:
            leaderboard.to_excel(writer, sheet_name="Leaderboard", index=False)
            try:
                if OPENPYXL_AVAILABLE:
                    sheet_lb = writer.sheets["Leaderboard"]
                    best_idx = leaderboard.iloc[0].name  # индекс строки лучшей модели
                    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    row_excel = best_idx + 2  # +2 из-за заголовка
                    for col_idx in range(1, leaderboard.shape[1] + 1):
                        cell = sheet_lb.cell(row=row_excel, column=col_idx)
                        cell.fill = fill_green
            except Exception as e:
                print(f"Ошибка при подсветке лучшей модели в Leaderboard: {e}")
        # Лист со статическими признаками
        if static_train is not None and not static_train.empty:
            static_train.to_excel(writer, sheet_name="StaticTrainFeatures", index=False)
        # Лист с информацией об ансамбле
        if ensemble_info_df is not None and not ensemble_info_df.empty:
            ensemble_info_df.to_excel(writer, sheet_name="WeightedEnsembleInfo", index=False)
    return excel_buffer
