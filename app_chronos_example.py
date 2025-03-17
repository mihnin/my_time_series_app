#!/usr/bin/env python
"""
Пример использования локальных моделей Chronos-Bolt в Docker-контейнере.
Этот скрипт демонстрирует, как использовать модели Chronos-Bolt, сохраненные локально, 
вместо загрузки их из Hugging Face в закрытой корпоративной среде.
"""
import os
import logging
import pandas as pd
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

# Импортируем нашу функциональность для работы с локальными моделями Chronos
from src.utils.chronos_models import get_local_model_path, modify_chronos_hyperparams, create_chronos_predictor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def load_example_data():
    """Загрузка примера данных для демонстрации"""
    try:
        # Пробуем загрузить данные из локального файла, если он существует
        local_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_data.xlsx")
        if os.path.exists(local_data_path):
            logger.info(f"Загружаем данные из локального файла: {local_data_path}")
            return TimeSeriesDataFrame.from_path(local_data_path)
        else:
            # Если локального файла нет, используем пример из AutoGluon
            logger.info("Локальный файл данных не найден, загружаем пример из AutoGluon")
            return TimeSeriesDataFrame.from_path(
                "https://autogluon.s3.amazonaws.com/datasets/timeseries/m4_hourly/train.csv"
            )
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        raise

def main():
    """Основная функция примера использования локальных моделей Chronos"""
    logger.info("Запуск примера использования локальных моделей Chronos-Bolt")
    
    try:
        # 1. Загрузка данных
        data = load_example_data()
        logger.info(f"Загружено {len(data)} временных рядов")
        logger.info(f"Частота данных: {data.freq}")
        
        # 2. Параметры прогнозирования
        prediction_length = 24  # Длина прогноза (например, 24 часа)
        
        # 3. Подход 1: Использование напрямую модифицированных гиперпараметров
        logger.info("ПОДХОД 1: Использование напрямую TimeSeriesPredictor с локальными моделями")
        
        # Создаем гиперпараметры с указанием модели Chronos-Bolt (Base)
        hyperparams = {
            "Chronos": {"model_path": "autogluon/chronos-bolt-base"}
        }
        
        # Модифицируем гиперпараметры для использования локальных моделей
        modified_hyperparams = modify_chronos_hyperparams(hyperparams)
        logger.info(f"Исходный путь к модели: {hyperparams['Chronos']['model_path']}")
        logger.info(f"Модифицированный путь к модели: {modified_hyperparams['Chronos']['model_path']}")
        
        # Создаем и обучаем TimeSeriesPredictor
        predictor1 = TimeSeriesPredictor(prediction_length=prediction_length)
        predictor1.fit(
            train_data=data,
            hyperparameters=modified_hyperparams,
            time_limit=60,  # Ограничение по времени в секундах
        )
        
        # Формируем прогноз
        predictions1 = predictor1.predict(data)
        logger.info(f"Прогноз получен, форма результата: {predictions1.shape}")
        
        # 4. Подход 2: Использование вспомогательной функции
        logger.info("\nПОДХОД 2: Использование вспомогательной функции create_chronos_predictor")
        
        # Создаем и обучаем предиктор через нашу вспомогательную функцию
        predictor2 = create_chronos_predictor(
            prediction_length=prediction_length,
            train_data=data,
            hyperparams={
                "Chronos": {"model_path": "bolt_small"}  # Используем bolt_small
            },
            time_limit=60,
        )
        
        # Формируем прогноз
        predictions2 = predictor2.predict(data)
        logger.info(f"Прогноз получен, форма результата: {predictions2.shape}")
        
        # 5. Сравнение результатов (для демонстрации)
        logger.info("\nСравнение прогнозов:")
        first_item_id = data.item_ids[0]
        
        logger.info(f"Прогноз модели bolt-base для {first_item_id}:")
        logger.info(predictions1.loc[first_item_id].head(5))
        
        logger.info(f"Прогноз модели bolt-small для {first_item_id}:")
        logger.info(predictions2.loc[first_item_id].head(5))
        
        # 6. Сохранение результатов (опционально)
        try:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            predictions1.to_csv(os.path.join(output_dir, "predictions_bolt_base.csv"))
            predictions2.to_csv(os.path.join(output_dir, "predictions_bolt_small.csv"))
            logger.info(f"Прогнозы сохранены в директорию: {output_dir}")
        except Exception as e:
            logger.warning(f"Не удалось сохранить прогнозы: {e}")
        
        logger.info("Пример успешно завершен!")
        return {
            "success": True,
            "predictions_bolt_base": predictions1,
            "predictions_bolt_small": predictions2
        }
        
    except Exception as e:
        logger.exception(f"Произошла ошибка: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    main()