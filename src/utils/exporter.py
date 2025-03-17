# src/utils/exporter.py
import io
import pandas as pd
from openpyxl.styles import PatternFill
import logging
import os
from pathlib import Path

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
    Формирует Excel-файл в памяти с результатами прогнозирования
    
    Аргументы:
        result (dict): Результат прогнозирования, содержащий forecasts и другие данные
    
    Возвращает:
        BytesIO: Объект BytesIO с Excel-файлом
    """
    excel_buffer = io.BytesIO()
    
    try:
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            # Проверяем успешность результата
            if not result.get('success', False):
                # Создаем лист с ошибкой
                pd.DataFrame([{"Ошибка": result.get('error', 'Неизвестная ошибка')}]).to_excel(
                    writer, sheet_name="Ошибка", index=False)
                return excel_buffer
            
            # Счетчик созданных листов
            sheets_created = 0
            
            # Лист с прогнозами для каждой целевой переменной
            sheet_idx = 0
            
            for target_col, forecast_data in result.get('forecasts', {}).items():
                predictions = forecast_data.get('predictions')
                if predictions is not None and not predictions.empty:
                    sheet_name = f"Прогноз_{target_col}"
                    if len(sheet_name) > 31:  # Ограничение Excel на длину имени листа
                        sheet_name = f"Прогноз_{sheet_idx}"
                        sheet_idx += 1
                    
                    # Сбрасываем индекс для экспорта в Excel
                    try:
                        predictions.reset_index().to_excel(writer, sheet_name=sheet_name, index=False)
                        sheets_created += 1
                    except Exception as e:
                        logging.error(f"Ошибка при сохранении прогноза для {target_col}: {e}")
                        pd.DataFrame([{"Ошибка": str(e)}]).to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Создаем пустую страницу с уведомлением
                    sheet_name = f"Прогноз_{target_col}_пусто"
                    if len(sheet_name) > 31:
                        sheet_name = f"Прогноз_{sheet_idx}_пусто"
                        sheet_idx += 1
                    
                    pd.DataFrame([{"Уведомление": f"Нет данных прогноза для {target_col}"}]).to_excel(
                        writer, sheet_name=sheet_name, index=False)
                    sheets_created += 1
                    logging.info(f"Создана пустая страница для {target_col}, т.к. данные отсутствуют")
            
            # Добавляем сводную информацию
            summary_data = []
            for target_col, forecast_data in result.get('forecasts', {}).items():
                summary_data.append({
                    "Целевая переменная": target_col,
                    "Дрейф концепции": "Обнаружен" if forecast_data.get('drift_detected', False) else "Не обнаружен",
                    "Комментарий": str(forecast_data.get('drift_info', {}))
                })
            
            if summary_data:
                pd.DataFrame(summary_data).to_excel(writer, sheet_name="Сводка", index=False)
                sheets_created += 1
            
            # Добавляем информацию о модуле с ошибкой, если она есть
            if 'module_error' in result:
                pd.DataFrame([{
                    "Тип ошибки": "Ошибка модуля AutoGluon",
                    "Описание": result.get('module_error', 'Неизвестная ошибка модуля'),
                    "Примечание": "Ошибка не критична и не влияет на точность прогнозов"
                }]).to_excel(writer, sheet_name="Ошибки модуля", index=False)
                sheets_created += 1
                logging.info("Добавлена информация об ошибках модуля AutoGluon")
            
            # Добавляем лидерборд, если он есть
            # Проверяем наличие лидерборда как прямого ключа или как атрибута предиктора
            leaderboard_df = None
            if 'leaderboard' in result and isinstance(result['leaderboard'], pd.DataFrame) and not result['leaderboard'].empty:
                leaderboard_df = result['leaderboard'].copy()
            elif 'predictor' in result and hasattr(result['predictor'], 'leaderboard'):
                try:
                    leaderboard_df = result['predictor'].leaderboard()
                except:
                    logging.warning("Не удалось получить лидерборд из предиктора")
            
            if leaderboard_df is not None and not leaderboard_df.empty:
                try:
                    # Округляем числовые колонки для лучшего отображения
                    for col in leaderboard_df.select_dtypes(include=['float']).columns:
                        leaderboard_df[col] = leaderboard_df[col].round(6)
                    
                    # Добавляем специальную колонку с рангом модели для удобства
                    leaderboard_df.insert(0, 'Ранг', range(1, len(leaderboard_df) + 1))
                    
                    # Улучшаем название колонки модели для удобства
                    if 'model' in leaderboard_df.columns:
                        leaderboard_df.rename(columns={'model': 'Модель'}, inplace=True)
                    
                    # Если в лидерборде есть скоры с отрицательными значениями (инвертированные метрики),
                    # добавляем колонку с абсолютными значениями для удобства
                    score_cols = [col for col in leaderboard_df.columns if 'score' in col.lower()]
                    for col in score_cols:
                        if (leaderboard_df[col] < 0).any():
                            abs_col = f'|{col}|'
                            leaderboard_df[abs_col] = leaderboard_df[col].abs()
                    
                    # Сохраняем лидерборд в Excel
                    leaderboard_df.to_excel(writer, sheet_name="Лидерборд", index=False)
                    
                    # Подсвечиваем лучшую модель
                    try:
                        sheet_lb = writer.sheets["Лидерборд"]
                        best_idx = 0  # первая строка - лучшая модель
                        fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                        row_excel = best_idx + 2  # +2 из-за заголовка и 1-индексации в Excel
                        for col_idx in range(1, leaderboard_df.shape[1] + 1):
                            cell = sheet_lb.cell(row=row_excel, column=col_idx)
                            cell.fill = fill_green
                    except Exception as e:
                        logging.warning(f"Не удалось подсветить лучшую модель в лидерборде: {e}")
                    
                    sheets_created += 1
                    logging.info("Добавлен лидерборд моделей")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении лидерборда: {e}")
                    pd.DataFrame([{"Ошибка": f"Ошибка при отображении лидерборда: {str(e)}"}]).to_excel(
                        writer, sheet_name="Лидерборд_ошибка", index=False)
            
            # Добавляем информацию о модели-ансамбле, если она присутствует
            # Проверяем наличие информации об ансамбле как прямого ключа или атрибута предиктора
            ensemble_df = None
            if 'ensemble_weights' in result and isinstance(result['ensemble_weights'], pd.DataFrame) and not result['ensemble_weights'].empty:
                ensemble_df = result['ensemble_weights'].copy()
                logging.info("Найдены готовые веса ансамбля в результате")
            elif 'ensemble_info' in result and isinstance(result['ensemble_info'], pd.DataFrame) and not result['ensemble_info'].empty:
                ensemble_df = result['ensemble_info'].copy()
                logging.info("Найдена информация об ансамбле в результате")
            elif 'predictor' in result and hasattr(result['predictor'], 'get_model_weights'):
                try:
                    ensemble_df = result['predictor'].get_model_weights()
                    logging.info("Веса ансамбля извлечены из предиктора")
                except Exception as e:
                    logging.warning(f"Не удалось получить информацию об ансамбле из предиктора: {e}")
            
            if ensemble_df is not None and not ensemble_df.empty:
                try:
                    # Улучшаем отображение весов в процентах
                    if 'Вес' in ensemble_df.columns:
                        ensemble_df['Вес (%)'] = (ensemble_df['Вес'] * 100).round(2)
                    
                    ensemble_df.to_excel(writer, sheet_name="Веса ансамбля", index=False)
                    sheets_created += 1
                    logging.info("Добавлена информация о модели типа ансамбль")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении информации об ансамбле: {e}")
                    pd.DataFrame([{"Ошибка": f"Ошибка при отображении информации об ансамбле: {str(e)}"}]).to_excel(
                        writer, sheet_name="Ансамбль_ошибка", index=False)
            
            # Добавляем детальную информацию о моделях, если она присутствует
            model_details_df = None
            if 'model_details' in result and isinstance(result['model_details'], pd.DataFrame) and not result['model_details'].empty:
                model_details_df = result['model_details'].copy()
                logging.info("Найдена детальная информация о моделях в результате")
            
            if model_details_df is not None and not model_details_df.empty:
                try:
                    # Пробуем красиво отформатировать параметры моделей
                    if 'Параметры' in model_details_df.columns:
                        model_details_df['Параметры'] = model_details_df['Параметры'].apply(
                            lambda x: str(x).replace('{', '\n{').replace(', ', ',\n ')
                        )
                    
                    model_details_df.to_excel(writer, sheet_name="Детали моделей", index=False)
                    sheets_created += 1
                    logging.info("Добавлена детальная информация о моделях")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении деталей моделей: {e}")
            
            # Добавляем информацию о модели-ансамбле, если она присутствует
            # Дополнительный извлечение весов моделей, если их нет в result
            ensemble_weights, model_details = None, None
            
            if 'predictor' in result:
                ensemble_weights, model_details = extract_ensemble_weights(result['predictor'])
            
            # Добавляем веса моделей ансамбля
            if ensemble_weights is not None and not ensemble_weights.empty:
                try:
                    # Преобразуем веса в проценты для лучшей читаемости
                    if 'Вес' in ensemble_weights.columns:
                        ensemble_weights['Вес (%)'] = (ensemble_weights['Вес'] * 100).round(2)
                        ensemble_weights = ensemble_weights.sort_values('Вес (%)', ascending=False)
                    
                    ensemble_weights.to_excel(writer, sheet_name="Веса ансамбля", index=False)
                    sheets_created += 1
                    logging.info("Добавлена информация о весах моделей в ансамбле")
                    
                    # Подсвечиваем модели с наибольшим весом
                    try:
                        sheet = writer.sheets["Веса ансамбля"]
                        fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                        # Подсвечиваем модели с весом выше среднего
                        mean_weight = ensemble_weights['Вес (%)'].mean()
                        for idx, row in enumerate(ensemble_weights.itertuples(), start=2):  # start=2 из-за заголовка
                            if row._3 > mean_weight:  # _3 - индекс столбца 'Вес (%)'
                                for col in range(1, len(ensemble_weights.columns) + 1):
                                    cell = sheet.cell(row=idx, column=col)
                                    cell.fill = fill_green
                    except Exception as e:
                        logging.warning(f"Не удалось подсветить важные модели в ансамбле: {e}")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении весов ансамбля: {e}")
            
            # Добавляем детальную информацию о моделях
            if model_details is not None and not model_details.empty:
                try:
                    # Пробуем красиво отформатировать параметры моделей
                    if 'Параметры' in model_details.columns:
                        model_details['Параметры'] = model_details['Параметры'].apply(
                            lambda x: str(x).replace('{', '\n{').replace(', ', ',\n ')
                        )
                    
                    model_details.to_excel(writer, sheet_name="Детали моделей", index=False)
                    sheets_created += 1
                    logging.info("Добавлена детальная информация о моделях в ансамбле")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении деталей моделей: {e}")
            
            # Если не создано ни одной страницы, создаем информационную страницу
            if sheets_created == 0:
                pd.DataFrame([{
                    "Информация": "Нет данных для отображения",
                    "Примечание": "Проверьте параметры и результаты прогнозирования"
                }]).to_excel(writer, sheet_name="Информация", index=False)
                logging.warning("В Excel-файле нет данных для отображения")
            
            # Определяем, является ли лучшая модель ансамблем
            best_model_name = None
            if 'predictor' in result and result['predictor'] is not None:
                try:
                    # Используем property model_best вместо устаревшего метода get_model_best
                    best_model_name = result['predictor'].model_best if hasattr(result['predictor'], 'model_best') else result['predictor'].get_model_best()
                    logging.info(f"Лучшая модель: {best_model_name}")
                except Exception as e:
                    logging.warning(f"Не удалось получить имя лучшей модели: {e}")
            
            # Если это ансамблевая модель, но информация не получена
            if best_model_name and "Ensemble" in best_model_name and ensemble_weights is None:
                pd.DataFrame([{
                    "Примечание": "Это ансамблевая модель",
                    "Ошибка": "Не удалось извлечь детальную информацию о составе ансамбля",
                    "Рекомендация": "Проверьте файлы моделей в директории AutogluonModels/TimeSeriesModel/models"
                }]).to_excel(writer, sheet_name="Инфо об ансамбле", index=False)
                sheets_created += 1
            
    except Exception as e:
        logging.exception(f"Ошибка при создании Excel файла: {e}")
        # В случае критической ошибки создаем новый буфер с сообщением об ошибке
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            pd.DataFrame([{"Ошибка": f"Не удалось создать файл: {str(e)}"}]).to_excel(
                writer, sheet_name="Ошибка", index=False)
    
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
        model_details = []
        
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
                                        
                                        model_details.append(model_info)
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
        details_df = pd.DataFrame(model_details) if model_details else None
        
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
