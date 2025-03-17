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
            
            # Добавляем лидерборд, если он есть
            if 'leaderboard' in result and isinstance(result['leaderboard'], pd.DataFrame) and not result['leaderboard'].empty:
                try:
                    leaderboard_df = result['leaderboard'].copy()
                    
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
                except Exception as e:
                    logging.error(f"Ошибка при сохранении лидерборда: {e}")
                    pd.DataFrame([{"Ошибка": f"Ошибка при отображении лидерборда: {str(e)}"}]).to_excel(
                        writer, sheet_name="Лидерборд_ошибка", index=False)
            
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
