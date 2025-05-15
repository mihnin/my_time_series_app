import pandas as pd
import logging
import time
import gc
from collections import Counter
from typing import Dict, Any, Optional

def validate_dataset(df: pd.DataFrame, 
                    dt_col: str, 
                    tgt_col: str, 
                    id_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Проверяет датасет на корректность и возвращает словарь с результатами валидации.
    """
    result = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    # Инициализируем outliers_count для безопасного использования в stats
    outliers_count = 0
    
    # Проверка наличия обязательных колонок
    required_cols = []
    if dt_col and dt_col != "<нет>":
        required_cols.append(dt_col)
    if tgt_col and tgt_col != "<нет>":
        required_cols.append(tgt_col)
    if id_col and id_col != "<нет>":
        required_cols.append(id_col)
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        result["is_valid"] = False
        result["errors"].append(f"Отсутствуют обязательные колонки: {', '.join(missing_cols)}")
        return result
    
    # Проверка типа данных в колонке с датой
    if dt_col and dt_col != "<нет>" and dt_col in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
            try:
                # Пытаемся преобразовать к datetime
                pd.to_datetime(df[dt_col], errors='raise')
            except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime) as e:
                result["is_valid"] = False
                result["errors"].append(f"Колонка {dt_col} содержит некорректные значения дат: {e}")
                return result
    
    # Проверка типа данных в колонке target
    if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[tgt_col]):
            result["is_valid"] = False
            result["errors"].append(f"Колонка {tgt_col} должна содержать числовые значения.")
            return result
    
    # Проверка на пропущенные значения
    if dt_col and dt_col != "<нет>" and dt_col in df.columns:
        missing_dt = df[dt_col].isna().sum()
        if missing_dt > 0:
            result["warnings"].append(f"Колонка {dt_col} содержит {missing_dt} пропущенных значений.")
    
    if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns:
        missing_tgt = df[tgt_col].isna().sum()
        if missing_tgt > 0:
            result["warnings"].append(f"Колонка {tgt_col} содержит {missing_tgt} пропущенных значений ({missing_tgt/len(df)*100:.2f}%).")
    
    # Анализ аномалий в целевой переменной
    if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns:
        q1 = df[tgt_col].quantile(0.25)
        q3 = df[tgt_col].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = df[(df[tgt_col] < lower_bound) | (df[tgt_col] > upper_bound)]
        outliers_count = len(outliers)
        
        if outliers_count > 0:
            result["warnings"].append(f"Обнаружено {outliers_count} выбросов в колонке {tgt_col} ({outliers_count/len(df)*100:.2f}%).")
    
    # Проверка временного ряда на непрерывность (ОПТИМИЗИРОВАНО)
    if dt_col and dt_col != "<нет>" and dt_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[dt_col]):
        if id_col and id_col != "<нет>" and id_col in df.columns:
            logging.info("Начало проверки непрерывности временных рядов по ID...")
            start_time = time.time()
            df_sorted = df[[id_col, dt_col]].sort_values(by=[id_col, dt_col])
            # Считаем разницу во времени внутри каждой группы ID
            df_sorted['time_diff'] = df_sorted.groupby(id_col)[dt_col].diff()

            # Убираем первую запись для каждой группы (у нее нет предыдущей)
            valid_diffs = df_sorted['time_diff'].dropna()

            if not valid_diffs.empty:
                # Находим наиболее частую разницу во времени (моду)
                # Используем Counter для эффективности на больших данных
                diff_counts = Counter(valid_diffs)
                most_common_diff = diff_counts.most_common(1)[0][0]
                logging.info("Наиболее частый интервал (частота): %s", most_common_diff)

                # Находим пропуски - строки, где разница больше наиболее частой
                # Добавляем небольшой допуск (1 секунда) для плавающей точки
                tolerance = pd.Timedelta(seconds=1)
                gaps = df_sorted[df_sorted['time_diff'] > (most_common_diff + tolerance)]
                num_gaps = len(gaps)
                
                if num_gaps > 0:
                    unique_gaps_count = gaps[id_col].nunique()
                    result["warnings"].append(f"Обнаружено {num_gaps} пропусков во временных рядах для {unique_gaps_count} ID (ожидаемый интервал: {most_common_diff}).")
                    # Опционально: можно добавить примеры ID с пропусками
                    # example_ids_with_gaps = gaps[id_col].unique()[:5]
                    # result["warnings"].append(f"Примеры ID с пропусками: {list(example_ids_with_gaps)}")
            else:
                logging.info("Недостаточно данных для определения частоты и пропусков (менее 2 точек на ID).")
                
            end_time = time.time()
            logging.info("Проверка непрерывности завершена за %.2f сек.", end_time - start_time)
            # Удаляем временную колонку и сортированный датафрейм для экономии памяти
            del df_sorted
            gc.collect()
        else:
            # Проверка непрерывности для одного временного ряда (без ID)
            logging.info("Начало проверки непрерывности одного временного ряда...")
            start_time = time.time()
            df_sorted = df[[dt_col]].sort_values(by=dt_col).drop_duplicates()
            if len(df_sorted) > 1:
                time_diffs = df_sorted[dt_col].diff().dropna()
                if not time_diffs.empty:
                    diff_counts = Counter(time_diffs)
                    most_common_diff = diff_counts.most_common(1)[0][0]
                    logging.info("Наиболее частый интервал (частота): %s", most_common_diff)
                    tolerance = pd.Timedelta(seconds=1)
                    gaps = df_sorted[df_sorted[dt_col].diff() > (most_common_diff + tolerance)]
                    num_gaps = len(gaps)
                    if num_gaps > 0:
                        result["warnings"].append(f"Обнаружено {num_gaps} пропусков во временном ряду (ожидаемый интервал: {most_common_diff}).")
                else:
                     logging.info("Недостаточно данных для определения частоты и пропусков (менее 2 точек).")
            else:
                logging.info("Недостаточно данных для проверки непрерывности (1 точка).")
                
            end_time = time.time()
            logging.info("Проверка непрерывности одного ряда завершена за %.2f сек.", end_time - start_time)
            del df_sorted
            gc.collect()
    
    # Рассчитываем и сохраняем статистики
    result["stats"] = {
        "rows_count": len(df),
        "target_min": df[tgt_col].min() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else None,
        "target_max": df[tgt_col].max() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else None,
        "target_mean": df[tgt_col].mean() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else None,
        "target_median": df[tgt_col].median() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else None,
        "target_std": df[tgt_col].std() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else None,
        "missing_values": {
            "dt_col": df[dt_col].isna().sum() if dt_col and dt_col != "<нет>" and dt_col in df.columns else 0,
            "tgt_col": df[tgt_col].isna().sum() if tgt_col and tgt_col != "<нет>" and tgt_col in df.columns else 0
        },
        "outliers_count": outliers_count if 'outliers_count' in locals() else 0
    }
    
    if id_col and id_col != "<нет>" and id_col in df.columns:
        result["stats"]["unique_ids"] = df[id_col].nunique()
    
    return result