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
            if 'ensemble_info' in result and isinstance(result['ensemble_info'], pd.DataFrame) and not result['ensemble_info'].empty:
                ensemble_df = result['ensemble_info'].copy()
            elif 'predictor' in result and hasattr(result['predictor'], 'get_model_weights'):
                try:
                    ensemble_df = result['predictor'].get_model_weights()
                except:
                    logging.warning("Не удалось получить информацию об ансамбле из предиктора")
            
            if ensemble_df is not None and not ensemble_df.empty:
                try:
                    ensemble_df.to_excel(writer, sheet_name="WeightedEnsembleInfo", index=False)
                    sheets_created += 1
                    logging.info("Добавлена информация о модели типа ансамбль")
                except Exception as e:
                    logging.error(f"Ошибка при сохранении информации об ансамбле: {e}")
                    pd.DataFrame([{"Ошибка": f"Ошибка при отображении информации об ансамбле: {str(e)}"}]).to_excel(
                        writer, sheet_name="Ансамбль_ошибка", index=False)
            
            # Добавляем информацию о модели-ансамбле, если она присутствует
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
                    
            # Если это ансамблевая модель, но информация не получена
            if best_model_name and "Ensemble" in best_model_name and ensemble_weights is None:
                pd.DataFrame([{
                    "Примечание": "Это ансамблевая модель",
                    "Ошибка": "Не удалось извлечь детальную информацию о составе ансамбля",
                    "Рекомендация": "Проверьте файлы моделей в директории AutogluonModels/TimeSeriesModel/models"
                }]).to_excel(writer, sheet_name="Инфо об ансамбле", index=False)
                sheets_created += 1
            
            # Если не создано ни одной страницы, создаем информационную страницу
            if sheets_created == 0:
                pd.DataFrame([{
                    "Информация": "Нет данных для отображения",
                    "Примечание": "Проверьте параметры и результаты прогнозирования"
                }]).to_excel(writer, sheet_name="Информация", index=False)
                logging.warning("В Excel-файле нет данных для отображения")
            
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
            return None, None
            
        # Пробуем получить информацию об ансамбле разными способами
        ensemble_weights = None
        model_details = []
        
        # Способ 1: Прямой метод get_model_weights()
        try:
            ensemble_weights = predictor.get_model_weights()
        except (AttributeError, Exception):
            pass
            
        # Способ 2: Через свойство best_model.weights и информацию о моделях
        if ensemble_weights is None:
            try:
                model_path = predictor.path
                best_model_name = predictor.get_model_best()
                
                if "Ensemble" in best_model_name:
                    # Получаем информацию о моделях
                    import os
                    import pickle
                    import pandas as pd
                    
                    models_dir = os.path.join(model_path, "models")
                    ensemble_file = None
                    
                    # Ищем файл ансамблевой модели
                    for filename in os.listdir(models_dir):
                        if "Ensemble" in filename and filename.endswith(".pkl"):
                            ensemble_file = os.path.join(models_dir, filename)
                            break
                    
                    if ensemble_file:
                        with open(ensemble_file, 'rb') as f:
                            ensemble_model = pickle.load(f)
                            
                        # Получаем веса
                        if hasattr(ensemble_model, 'weights'):
                            weights = ensemble_model.weights
                            if isinstance(weights, dict):
                                ensemble_weights = pd.DataFrame({
                                    'Модель': list(weights.keys()),
                                    'Вес': list(weights.values())
                                })
                                ensemble_weights = ensemble_weights.sort_values('Вес', ascending=False)
                                
                                # Собираем детальную информацию о моделях
                                for model_name in weights.keys():
                                    model_info = {'Название модели': model_name}
                                    
                                    # Ищем файл модели
                                    model_file = None
                                    for filename in os.listdir(models_dir):
                                        if filename.startswith(model_name) and filename.endswith(".pkl"):
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
                                            
                                            # Получаем метрики модели, если есть
                                            if hasattr(model, 'score'):
                                                model_info['Метрика'] = str(model.score)
                                        except Exception:
                                            pass
                                    
                                    model_details.append(model_info)
                
            except Exception as e:
                logging.warning(f"Ошибка при получении детальной информации о моделях: {e}")
        
        # Создаем DataFrame с детальной информацией
        details_df = pd.DataFrame(model_details) if model_details else None
        
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
