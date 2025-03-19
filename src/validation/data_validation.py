# src/validation/data_validation.py
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)

def validate_dataset(df: pd.DataFrame, required_columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Выполняет базовую валидацию DataFrame на корректность структуры
    
    Args:
        df (pd.DataFrame): Проверяемый DataFrame
        required_columns (List[str], optional): Список обязательных колонок
        
    Returns:
        Dict[str, Any]: Словарь с результатами валидации
            {
                "valid": bool - корректность данных,
                "error": str or None - описание ошибки, если есть,
                "warnings": List[str] - предупреждения, если есть,
                "stats": Dict - статистика по данным
            }
    """
    if df is None or df.empty:
        return {
            "valid": False,
            "error": "Датафрейм пуст или не предоставлен",
            "warnings": [],
            "stats": {}
        }
    
    # Статистика по данным
    stats = {
        "shape": df.shape,
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "memory_usage": df.memory_usage(deep=True).sum() / (1024 * 1024)  # в МБ
    }
    
    # Предупреждения
    warnings = []
    
    # Проверка требуемых колонок
    if required_columns:
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return {
                "valid": False,
                "error": f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}",
                "warnings": warnings,
                "stats": stats
            }
    
    # Проверка на наличие пропусков
    null_counts = df.isnull().sum()
    columns_with_nulls = null_counts[null_counts > 0].index.tolist()
    if columns_with_nulls:
        missing_pct = {col: null_counts[col] / len(df) * 100 for col in columns_with_nulls}
        high_missing_cols = [col for col, pct in missing_pct.items() if pct > 30]
        
        if high_missing_cols:
            warnings.append(f"Следующие колонки имеют более 30% пропущенных значений: {', '.join(high_missing_cols)}")
        else:
            warnings.append(f"Обнаружены пропуски в колонках: {', '.join(columns_with_nulls)}")
    
    # Проверка на дубликаты строк
    duplicate_count = df.duplicated().sum()
    if duplicate_count > 0:
        warnings.append(f"Обнаружено {duplicate_count} дубликатов строк ({duplicate_count / len(df) * 100:.2f}%)")
    
    # Проверка на экстремальные значения в числовых колонках
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        try:
            q1 = df[col].quantile(0.01)
            q3 = df[col].quantile(0.99)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            outlier_count = len(outliers)
            
            if outlier_count > 0:
                outlier_pct = outlier_count / len(df) * 100
                if outlier_pct > 5:
                    warnings.append(f"Колонка '{col}' содержит {outlier_count} выбросов ({outlier_pct:.2f}%)")
        except Exception as e:
            logger.warning(f"Не удалось проверить выбросы в колонке '{col}': {str(e)}")
    
    # Результат валидации
    return {
        "valid": True,  # Базовая валидация успешна
        "error": None,
        "warnings": warnings,
        "stats": stats
    }

def validate_forecasting_data(df: pd.DataFrame, timestamp_col: str = "timestamp", 
                            id_col: str = "item_id", target_col: str = "target") -> Dict[str, Any]:
    """
    Проверяет данные на соответствие требованиям для прогнозирования временных рядов
    
    Args:
        df (pd.DataFrame): Проверяемый DataFrame
        timestamp_col (str): Название колонки с временной меткой
        id_col (str): Название колонки с идентификатором временного ряда
        target_col (str): Название колонки с целевым значением
        
    Returns:
        Dict[str, Any]: Словарь с результатами валидации
    """
    # Базовая валидация
    required_columns = [timestamp_col, id_col, target_col]
    base_validation = validate_dataset(df, required_columns)
    
    if not base_validation["valid"]:
        return base_validation
    
    warnings = base_validation["warnings"]
    stats = base_validation["stats"]
    
    # Проверка типа данных для колонки с датой
    try:
        # Пробуем преобразовать к datetime, если еще не datetime
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            try:
                pd.to_datetime(df[timestamp_col])
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Не удалось преобразовать колонку '{timestamp_col}' к типу datetime: {str(e)}",
                    "warnings": warnings,
                    "stats": stats
                }
        
        # Проверка на хронологический порядок для каждого ID
        unordered_ids = []
        for id_val in df[id_col].unique():
            subset = df[df[id_col] == id_val]
            if not subset[timestamp_col].is_monotonic_increasing:
                unordered_ids.append(str(id_val))
                if len(unordered_ids) >= 5:  # Ограничиваем количество выводимых ID
                    break
        
        if unordered_ids:
            id_msg = ", ".join(unordered_ids[:5])
            if len(unordered_ids) > 5:
                id_msg += f" и еще {len(unordered_ids) - 5}"
            warnings.append(f"Временные метки не отсортированы для ID: {id_msg}")
    
    except Exception as e:
        return {
            "valid": False,
            "error": f"Ошибка при проверке временных меток: {str(e)}",
            "warnings": warnings,
            "stats": stats
        }
    
    # Проверка на пропуски в целевой переменной
    if df[target_col].isnull().sum() > 0:
        missing_count = df[target_col].isnull().sum()
        missing_pct = missing_count / len(df) * 100
        if missing_pct > 30:
            return {
                "valid": False,
                "error": f"Слишком много пропусков в целевой переменной '{target_col}': {missing_count} ({missing_pct:.2f}%)",
                "warnings": warnings,
                "stats": stats
            }
        else:
            warnings.append(f"Обнаружены пропуски в целевой переменной '{target_col}': {missing_count} ({missing_pct:.2f}%)")
    
    # Проверка на инвариантность целевой переменной
    if df[target_col].nunique() <= 1:
        return {
            "valid": False,
            "error": f"Целевая переменная '{target_col}' имеет только одно уникальное значение",
            "warnings": warnings,
            "stats": stats
        }
    
    # Проверка на дубликаты по ID и временной метке
    duplicates = df.duplicated(subset=[id_col, timestamp_col], keep=False)
    if duplicates.any():
        dup_count = duplicates.sum()
        dup_pct = dup_count / len(df) * 100
        
        # Получаем примеры дубликатов
        dup_examples = df[duplicates].sort_values([id_col, timestamp_col]).head(5)
        dup_info = []
        for _, row in dup_examples.iterrows():
            dup_info.append(f"{row[id_col]} на {row[timestamp_col]}")
        
        if dup_pct > 5:
            return {
                "valid": False,
                "error": f"Обнаружено много дубликатов по ID и дате: {dup_count} ({dup_pct:.2f}%). Примеры: {', '.join(dup_info)}",
                "warnings": warnings,
                "stats": stats
            }
        else:
            warnings.append(f"Обнаружены дубликаты по ID и дате: {dup_count} ({dup_pct:.2f}%). Примеры: {', '.join(dup_info)}")
    
    # Анализ частоты данных
    try:
        # Проверяем регулярность временного ряда для каждого ID
        irregular_ids = []
        for id_val in df[id_col].unique()[:10]:  # Проверяем первые 10 ID для экономии времени
            subset = df[df[id_col] == id_val].sort_values(timestamp_col)
            if len(subset) >= 3:
                # Вычисляем разницы между соседними временными метками
                diffs = subset[timestamp_col].diff().dropna()
                # Проверяем разнообразие интервалов (не должно быть слишком много разных)
                unique_intervals = diffs.unique()
                if len(unique_intervals) > min(5, len(diffs) // 2):
                    irregular_ids.append(str(id_val))
        
        if irregular_ids:
            id_msg = ", ".join(irregular_ids[:5])
            if len(irregular_ids) > 5:
                id_msg += f" и еще {len(irregular_ids) - 5}"
            warnings.append(f"Обнаружены нерегулярные интервалы между временными метками для ID: {id_msg}")
    except Exception as e:
        logger.warning(f"Не удалось проверить регулярность временного ряда: {str(e)}")
    
    # Проверка количества точек во временном ряде
    id_counts = df.groupby(id_col).size()
    min_points = id_counts.min()
    if min_points < 3:
        warnings.append(f"Минимальное количество точек в ряду: {min_points}. Рекомендуется не менее 10 точек для качественного прогнозирования.")
    
    # Обогащаем статистику информацией о временных рядах
    stats.update({
        "num_series": len(df[id_col].unique()),
        "min_points_per_series": min_points,
        "max_points_per_series": id_counts.max(),
        "avg_points_per_series": id_counts.mean(),
        "time_range": [df[timestamp_col].min(), df[timestamp_col].max()],
        "target_range": [df[target_col].min(), df[target_col].max()]
    })
    
    # Итоговый результат
    return {
        "valid": True,
        "error": None,
        "warnings": warnings,
        "stats": stats
    }

def display_validation_results(results: Dict[str, Any]) -> None:
    """
    Отображает результаты валидации в пользовательском интерфейсе с использованием streamlit
    
    Args:
        results (Dict[str, Any]): Результаты валидации из функций validate_dataset или validate_forecasting_data
    """
    try:
        import streamlit as st
        
        if results["valid"]:
            st.success("✅ Данные прошли валидацию успешно")
        else:
            st.error(f"❌ Ошибка валидации: {results['error']}")
            st.stop()
        
        # Отображаем предупреждения, если они есть
        if results["warnings"]:
            with st.expander("⚠️ Предупреждения", expanded=True):
                for i, warning in enumerate(results["warnings"], 1):
                    st.warning(f"{i}. {warning}")
        
        # Отображаем статистику
        with st.expander("📊 Статистика по данным", expanded=False):
            st.write(f"Размер данных: {results['stats']['shape'][0]} строк, {results['stats']['shape'][1]} столбцов")
            st.write(f"Использование памяти: {results['stats']['memory_usage']:.2f} МБ")
            
            if "num_series" in results["stats"]:
                st.write(f"Количество временных рядов: {results['stats']['num_series']}")
                st.write(f"Точек на ряд: мин = {results['stats']['min_points_per_series']}, "
                         f"макс = {results['stats']['max_points_per_series']}, "
                         f"сред = {results['stats']['avg_points_per_series']:.1f}")
                
                # Отображаем временной диапазон
                if "time_range" in results["stats"]:
                    time_range = results["stats"]["time_range"]
                    st.write(f"Временной диапазон: от {time_range[0]} до {time_range[1]}")
            
            # Отображаем информацию о пропусках
            missing_values = results["stats"].get("missing_values", {})
            if missing_values:
                cols_with_missing = [col for col, count in missing_values.items() if count > 0]
                if cols_with_missing:
                    st.write("Колонки с пропущенными значениями:")
                    for col in cols_with_missing:
                        st.write(f" - {col}: {missing_values[col]} ({missing_values[col]/results['stats']['shape'][0]*100:.1f}%)")
    
    except ImportError:
        # Если streamlit не доступен, выводим результаты в лог
        logger.info("Результаты валидации:")
        if results["valid"]:
            logger.info("✅ Данные прошли валидацию успешно")
        else:
            logger.error(f"❌ Ошибка валидации: {results['error']}")
        
        if results["warnings"]:
            logger.warning("⚠️ Предупреждения:")
            for i, warning in enumerate(results["warnings"], 1):
                logger.warning(f"{i}. {warning}")
        
        logger.info(f"Статистика: {results['stats']}")

def check_data_readiness(df: pd.DataFrame, predict_periods: int = 10, 
                       timestamp_col: str = "timestamp", id_col: str = "item_id") -> Dict[str, Any]:
    """
    Проверяет готовность данных для прогноза, включая оценку полноты данных относительно горизонта прогноза
    
    Args:
        df (pd.DataFrame): Данные для проверки
        predict_periods (int): Горизонт прогнозирования
        timestamp_col (str): Имя колонки с временной меткой
        id_col (str): Имя колонки с идентификатором временного ряда
        
    Returns:
        Dict[str, Any]: Результат проверки с информацией о готовности данных
    """
    result = {
        "ready": True,
        "error": None,
        "warnings": [],
        "details": {}
    }
    
    if df is None or df.empty:
        return {
            "ready": False,
            "error": "Данные отсутствуют или пусты",
            "warnings": [],
            "details": {}
        }
    
    # Проверяем наличие необходимых колонок
    required_cols = [timestamp_col, id_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {
            "ready": False,
            "error": f"Отсутствуют обязательные колонки: {', '.join(missing_cols)}",
            "warnings": [],
            "details": {}
        }
    
    # Преобразуем временные метки если нужно
    df_copy = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_copy[timestamp_col]):
        try:
            df_copy[timestamp_col] = pd.to_datetime(df_copy[timestamp_col])
        except Exception as e:
            return {
                "ready": False,
                "error": f"Не удалось преобразовать колонку '{timestamp_col}' к типу datetime: {str(e)}",
                "warnings": [],
                "details": {}
            }
    
    # Проверяем каждый временной ряд
    series_stats = {}
    inadequate_series = []
    
    for id_val in df_copy[id_col].unique():
        series_df = df_copy[df_copy[id_col] == id_val].sort_values(timestamp_col)
        
        # Получаем статистику по ряду
        num_points = len(series_df)
        min_date = series_df[timestamp_col].min()
        max_date = series_df[timestamp_col].max()
        date_range = (max_date - min_date).total_seconds() / 86400  # в днях
        
        # Собираем статистику
        series_stats[id_val] = {
            "points": num_points,
            "start_date": min_date,
            "end_date": max_date,
            "date_range_days": date_range
        }
        
        # Проверка достаточности данных для прогноза
        if num_points < predict_periods * 2:  # Рекомендуется иметь в 2 раза больше точек, чем горизонт прогноза
            inadequate_series.append(id_val)
            
            # Добавляем оценку нехватки данных
            series_stats[id_val]["sufficient"] = False
            series_stats[id_val]["missing_points"] = predict_periods * 2 - num_points
        else:
            series_stats[id_val]["sufficient"] = True
            series_stats[id_val]["missing_points"] = 0
    
    # Генерация предупреждений
    if inadequate_series:
        result["warnings"].append(
            f"Обнаружены {len(inadequate_series)} ряда(ов) с недостаточным количеством данных для надежного прогноза."
        )
        
        # Если более 30% рядов имеют недостаточно данных, добавляем предупреждение
        if len(inadequate_series) / len(series_stats) > 0.3:
            result["warnings"].append(
                "Более 30% рядов имеют недостаточно данных. Качество прогноза может быть низким."
            )
    
    # Добавляем детали для дальнейшего анализа
    result["details"] = {
        "series_stats": series_stats,
        "inadequate_series": inadequate_series,
        "total_series": len(series_stats),
        "inadequate_count": len(inadequate_series),
        "inadequate_percent": len(inadequate_series) / len(series_stats) * 100 if series_stats else 0
    }
    
    return result

def suggest_data_improvements(validation_results: Dict[str, Any]) -> List[str]:
    """
    На основе результатов валидации предлагает улучшения данных
    
    Args:
        validation_results (Dict[str, Any]): Результаты валидации из функций validate_dataset или validate_forecasting_data
        
    Returns:
        List[str]: Список рекомендаций по улучшению данных
    """
    suggestions = []
    
    # Если данные не прошли валидацию
    if not validation_results["valid"]:
        error = validation_results["error"]
        
        # Рекомендации в зависимости от типа ошибки
        if "колонк" in error and "отсутству" in error:
            suggestions.append("Добавьте отсутствующие колонки в данные или выберите правильные имена колонок в интерфейсе")
        
        elif "преобразовать" in error and "datetime" in error:
            suggestions.append("Проверьте формат даты/времени. Убедитесь, что он соответствует стандартному формату ISO или другому распознаваемому формату")
        
        elif "дубликат" in error:
            suggestions.append("Удалите дубликаты строк или агрегируйте значения для одинаковых пар (ID, дата)")
        
        elif "пропуск" in error or "missing" in error:
            suggestions.append("Заполните пропуски в данных, используя методы интерполяции или другие подходящие техники")
        
        else:
            suggestions.append("Исправьте указанную ошибку и повторите попытку")
    
    # Рекомендации на основе предупреждений
    for warning in validation_results.get("warnings", []):
        if "пропуск" in warning:
            suggestions.append("Заполните пропущенные значения используя методы: ffill, bfill, interpolate или mean")
            
        elif "дубликат" in warning:
            suggestions.append("Рассмотрите возможность удаления или агрегации дубликатов")
            
        elif "выброс" in warning:
            suggestions.append("Рассмотрите возможность обработки выбросов: удаление, винзоризация или другие методы")
            
        elif "нерегулярн" in warning and "интервал" in warning:
            suggestions.append("Преобразуйте данные к регулярному временному ряду с постоянным интервалом")
            
        elif "Минимальное количество точек" in warning:
            suggestions.append("Добавьте больше исторических данных для каждого ряда или уменьшите горизонт прогнозирования")
            
        elif "не отсортирован" in warning:
            suggestions.append("Отсортируйте данные по ID и временной метке для каждого ряда")
    
    # Если нет конкретных предупреждений, но данные валидны
    if validation_results["valid"] and not suggestions:
        # Проверяем статистику
        stats = validation_results.get("stats", {})
        
        # Проверка на малое количество точек в ряду
        if stats.get("min_points_per_series", 0) < 20:
            suggestions.append("Увеличьте количество точек в каждом ряду для более точного прогнозирования")
        
        # Проверка на большой разброс в количестве точек между рядами
        if stats.get("max_points_per_series", 0) > stats.get("min_points_per_series", 0) * 10:
            suggestions.append("Сбалансируйте количество точек между рядами или используйте отдельные модели для разных групп рядов")
    
    # Добавляем общие рекомендации для улучшения прогнозирования
    if not suggestions:
        suggestions.append("Рассмотрите возможность добавления внешних факторов (праздники, сезонность, погода) для улучшения качества прогноза")
        suggestions.append("Попробуйте увеличить частоту данных для получения более детального прогноза")
    
    return suggestions

def plot_target_distribution(df: pd.DataFrame, target_col: str = "target", 
                            id_col: str = "item_id", log_scale: bool = False):
    """
    Визуализирует распределение целевой переменной
    
    Args:
        df (pd.DataFrame): Данные для визуализации
        target_col (str): Имя колонки с целевой переменной
        id_col (str): Имя колонки с идентификатором временного ряда
        log_scale (bool): Использовать логарифмическую шкалу для оси Y
        
    Returns:
        plotly.graph_objects.Figure: Объект графика
    """
    import plotly.express as px
    import plotly.graph_objects as go
    
    try:
        # Создаем копию данных для безопасности
        data = df.copy()
        
        if target_col not in data.columns:
            logger.error(f"Колонка {target_col} не найдена в данных")
            return go.Figure().add_annotation(
                text=f"Ошибка: Колонка {target_col} не найдена в данных",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Создаем гистограмму
        fig = px.histogram(
            data, 
            x=target_col,
            title=f"Распределение целевой переменной '{target_col}'",
            labels={target_col: "Значение"},
            opacity=0.7,
            marginal="box"
        )
        
        # Настраиваем логарифмическую шкалу, если запрошено
        if log_scale and data[target_col].min() > 0:
            fig.update_layout(yaxis_type="log")
            fig.update_layout(title=f"Распределение целевой переменной '{target_col}' (логарифмическая шкала)")
        
        # Добавляем статистические линии
        mean_val = data[target_col].mean()
        median_val = data[target_col].median()
        
        fig.add_vline(x=mean_val, line_dash="dash", line_color="red",
                      annotation_text=f"Среднее: {mean_val:.2f}", 
                      annotation_position="top right")
        fig.add_vline(x=median_val, line_dash="dash", line_color="green",
                      annotation_text=f"Медиана: {median_val:.2f}", 
                      annotation_position="top left")
        
        # Добавляем информацию о данных
        fig.add_annotation(
            text=f"<b>Статистика:</b><br>" +
                 f"Количество рядов: {len(data[id_col].unique())}<br>" +
                 f"Всего наблюдений: {len(data)}<br>" +
                 f"Мин: {data[target_col].min():.2f}<br>" +
                 f"Макс: {data[target_col].max():.2f}<br>" +
                 f"Среднее: {mean_val:.2f}<br>" +
                 f"Стд. откл.: {data[target_col].std():.2f}",
            align="left",
            showarrow=False,
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            bordercolor="black", borderwidth=1,
            bgcolor="white", opacity=0.8
        )
        
        fig.update_layout(height=600, width=800)
        return fig
        
    except Exception as e:
        logger.error(f"Ошибка при построении распределения: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Ошибка при построении распределения: {str(e)}",
            showarrow=False, xref="paper", yref="paper"
        )
        return fig

def plot_target_boxplot(df: pd.DataFrame, target_col: str = "target", 
                       id_col: str = "item_id", max_series: int = 20):
    """
    Построение диаграммы box-plot для каждого временного ряда
    
    Args:
        df (pd.DataFrame): Данные для визуализации
        target_col (str): Имя колонки с целевой переменной
        id_col (str): Имя колонки с идентификатором временного ряда
        max_series (int): Максимальное количество рядов для отображения
        
    Returns:
        plotly.graph_objects.Figure: Объект графика
    """
    import plotly.express as px
    import plotly.graph_objects as go
    
    try:
        data = df.copy()
        
        if target_col not in data.columns or id_col not in data.columns:
            missing_cols = []
            if target_col not in data.columns:
                missing_cols.append(target_col)
            if id_col not in data.columns:
                missing_cols.append(id_col)
                
            logger.error(f"Колонки {', '.join(missing_cols)} не найдены в данных")
            return go.Figure().add_annotation(
                text=f"Ошибка: Колонки {', '.join(missing_cols)} не найдены в данных",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Получаем уникальные ID временных рядов
        series_ids = data[id_col].unique()
        
        # Если рядов слишком много, берем только первые max_series
        if len(series_ids) > max_series:
            series_ids = series_ids[:max_series]
            data = data[data[id_col].isin(series_ids)]
            
        # Создаем диаграмму box-plot
        fig = px.box(
            data, 
            x=id_col, 
            y=target_col,
            title=f"Распределение целевой переменной '{target_col}' по временным рядам",
            labels={
                id_col: "Идентификатор ряда",
                target_col: "Значение целевой переменной"
            },
            points="all", # Показывать все точки
            color=id_col # Разные цвета для разных рядов
        )
        
        fig.update_layout(
            showlegend=False,
            height=600,
            width=max(800, len(series_ids) * 40) # Адаптивная ширина
        )
        
        if len(series_ids) > max_series:
            fig.add_annotation(
                text=f"Показаны только {max_series} из {len(df[id_col].unique())} временных рядов",
                showarrow=False, xref="paper", yref="paper",
                x=0.5, y=1.05
            )
            
        return fig
    
    except Exception as e:
        logger.error(f"Ошибка при построении box-plot: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Ошибка при построении box-plot: {str(e)}",
            showarrow=False, xref="paper", yref="paper"
        )
        return fig

def plot_target_time_series(df: pd.DataFrame, timestamp_col: str = "timestamp", 
                           target_col: str = "target", id_col: str = "item_id", 
                           max_series: int = 5):
    """
    Визуализирует временные ряды
    
    Args:
        df (pd.DataFrame): Данные для визуализации
        timestamp_col (str): Имя колонки с временной меткой
        target_col (str): Имя колонки с целевой переменной
        id_col (str): Имя колонки с идентификатором временного ряда
        max_series (int): Максимальное количество рядов для отображения
        
    Returns:
        plotly.graph_objects.Figure: Объект графика
    """
    import plotly.express as px
    import plotly.graph_objects as go
    
    try:
        data = df.copy()
        
        required_cols = [timestamp_col, target_col, id_col]
        missing_cols = [col for col in required_cols if col not in data.columns]
        
        if missing_cols:
            logger.error(f"Колонки {', '.join(missing_cols)} не найдены в данных")
            return go.Figure().add_annotation(
                text=f"Ошибка: Колонки {', '.join(missing_cols)} не найдены в данных",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Сортируем по времени
        try:
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
            data = data.sort_values(by=timestamp_col)
        except Exception as e:
            logger.warning(f"Ошибка при конвертации временных меток: {e}")
            # Продолжим без сортировки, если не получилось
        
        # Получаем уникальные ID временных рядов
        series_ids = data[id_col].unique()
        
        # Если рядов слишком много, берем только первые max_series
        if len(series_ids) > max_series:
            series_ids = series_ids[:max_series]
            data = data[data[id_col].isin(series_ids)]
        
        # Создаем график линий
        fig = px.line(
            data, 
            x=timestamp_col, 
            y=target_col,
            color=id_col,
            title=f"Временные ряды целевой переменной '{target_col}'",
            labels={
                timestamp_col: "Время",
                target_col: "Значение",
                id_col: "Идентификатор ряда"
            },
            markers=True
        )
        
        fig.update_layout(
            height=600,
            width=1000,
            hovermode="x unified"
        )
        
        if len(series_ids) > max_series:
            fig.add_annotation(
                text=f"Показаны только {max_series} из {len(df[id_col].unique())} временных рядов",
                showarrow=False, xref="paper", yref="paper",
                x=0.5, y=1.05
            )
            
        return fig
    
    except Exception as e:
        logger.error(f"Ошибка при построении временных рядов: {e}")
        fig = go.Figure()
        fig.add_annotation(
            text=f"Ошибка при построении временных рядов: {str(e)}",
            showarrow=False, xref="paper", yref="paper"
        )
        return fig

def analyze_seasonal_patterns(df: pd.DataFrame, timestamp_col: str = "timestamp", 
                             target_col: str = "target", id_col: str = "item_id", 
                             freq: str = "D", periods: List[str] = ['day', 'week', 'month']):
    """
    Анализирует сезонные паттерны во временных рядах
    
    Args:
        df (pd.DataFrame): Данные для анализа
        timestamp_col (str): Имя колонки с временной меткой
        target_col (str): Имя колонки с целевой переменной
        id_col (str): Имя колонки с идентификатором временного ряда
        freq (str): Частота временного ряда ('D' - день, 'M' - месяц, и т.д.)
        periods (List[str]): Периоды для анализа ['day', 'week', 'month', 'quarter', 'year']
        
    Returns:
        Tuple[Dict[str, Any], plotly.graph_objects.Figure]: Результаты анализа и график
    """
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    try:
        data = df.copy()
        
        required_cols = [timestamp_col, target_col, id_col]
        missing_cols = [col for col in required_cols if col not in data.columns]
        
        if missing_cols:
            logger.error(f"Колонки {', '.join(missing_cols)} не найдены в данных")
            return {}, go.Figure().add_annotation(
                text=f"Ошибка: Колонки {', '.join(missing_cols)} не найдены в данных",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Конвертируем временные метки
        try:
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
            data = data.sort_values(by=timestamp_col)
        except Exception as e:
            logger.error(f"Ошибка при конвертации временных меток: {e}")
            return {}, go.Figure().add_annotation(
                text=f"Ошибка при конвертации временных меток: {str(e)}",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Создаем дополнительные временные признаки
        seasonal_components = {}
        data['hour'] = data[timestamp_col].dt.hour
        data['day'] = data[timestamp_col].dt.day
        data['weekday'] = data[timestamp_col].dt.weekday
        data['week'] = data[timestamp_col].dt.isocalendar().week
        data['month'] = data[timestamp_col].dt.month
        data['quarter'] = data[timestamp_col].dt.quarter
        data['year'] = data[timestamp_col].dt.year
        
        # Анализируем сезонность по каждому периоду
        valid_periods = [p for p in periods if p in ['hour', 'day', 'weekday', 'week', 'month', 'quarter', 'year']]
        
        if not valid_periods:
            logger.warning("Не указаны корректные периоды для анализа")
            valid_periods = ['day', 'month']
        
        # Создаем подграфики для каждого периода
        n_plots = len(valid_periods)
        fig = make_subplots(rows=n_plots, cols=1, 
                           subplot_titles=[f"Сезонность по {p}" for p in valid_periods],
                           vertical_spacing=0.1)
        
        # Словарь для описания периодов
        period_names = {
            'hour': 'часу', 
            'day': 'дню месяца', 
            'weekday': 'дню недели',
            'week': 'неделе', 
            'month': 'месяцу', 
            'quarter': 'кварталу', 
            'year': 'году'
        }
        
        # Словарь для меток на осях
        axis_labels = {
            'hour': {i: f"{i}:00" for i in range(24)},
            'day': {i: str(i) for i in range(1, 32)},
            'weekday': {0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'},
            'week': {i: str(i) for i in range(1, 54)},
            'month': {1: 'Янв', 2: 'Фев', 3: 'Март', 4: 'Апр', 5: 'Май', 6: 'Июнь', 
                     7: 'Июль', 8: 'Авг', 9: 'Сент', 10: 'Окт', 11: 'Нояб', 12: 'Дек'},
            'quarter': {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'},
            'year': {i: str(i) for i in range(1900, 2100)}
        }
        
        # Анализируем каждый период
        for i, period in enumerate(valid_periods):
            # Группируем данные по периоду и вычисляем среднее, медиану, мин и макс
            grouped = data.groupby(period)[target_col].agg(['mean', 'median', 'min', 'max', 'count']).reset_index()
            seasonal_components[period] = grouped.to_dict('records')
            
            # Добавляем боксплот на график
            box_trace = go.Box(
                x=data[period],
                y=data[target_col],
                name=f"{period_names.get(period, period)}",
                boxmean=True,
                marker_color='lightseagreen',
                showlegend=False
            )
            
            line_trace = go.Scatter(
                x=grouped[period],
                y=grouped['mean'],
                mode='lines+markers',
                name='Среднее',
                line=dict(color='red', width=2),
                showlegend=False if i > 0 else True
            )
            
            fig.add_trace(box_trace, row=i+1, col=1)
            fig.add_trace(line_trace, row=i+1, col=1)
            
            # Настройка осей
            if period in axis_labels:
                ticks = list(axis_labels[period].items())
                ticks.sort(key=lambda x: x[0])
                tickvals = [t[0] for t in ticks]
                ticktext = [t[1] for t in ticks]
                
                fig.update_xaxes(
                    tickmode='array',
                    tickvals=tickvals,
                    ticktext=ticktext,
                    row=i+1, col=1
                )
            
            fig.update_yaxes(title_text=target_col, row=i+1, col=1)
            
        # Настраиваем общий вид графика
        fig.update_layout(
            height=300 * n_plots,
            width=1000,
            title=f"Анализ сезонности целевой переменной '{target_col}'",
            showlegend=True
        )
        
        # Возвращаем результаты анализа и график
        results = {
            "seasonal_components": seasonal_components,
            "periods_analyzed": valid_periods
        }
        
        return results, fig
    
    except Exception as e:
        logger.error(f"Ошибка при анализе сезонности: {e}")
        return {}, go.Figure().add_annotation(
            text=f"Ошибка при анализе сезонности: {str(e)}",
            showarrow=False, xref="paper", yref="paper"
        )

def detect_autocorrelation(df: pd.DataFrame, timestamp_col: str = "timestamp", 
                          target_col: str = "target", id_col: str = "item_id", 
                          max_lag: int = 20, max_series: int = 3):
    """
    Анализирует автокорреляцию во временных рядах
    
    Args:
        df (pd.DataFrame): Данные для анализа
        timestamp_col (str): Имя колонки с временной меткой
        target_col (str): Имя колонки с целевой переменной
        id_col (str): Имя колонки с идентификатором временного ряда
        max_lag (int): Максимальный лаг для анализа
        max_series (int): Максимальное количество рядов для анализа
        
    Returns:
        Tuple[Dict[str, Any], plotly.graph_objects.Figure]: Результаты анализа и график
    """
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from statsmodels.tsa.stattools import acf, pacf
    
    try:
        data = df.copy()
        
        required_cols = [timestamp_col, target_col, id_col]
        missing_cols = [col for col in required_cols if col not in data.columns]
        
        if missing_cols:
            logger.error(f"Колонки {', '.join(missing_cols)} не найдены в данных")
            return {}, go.Figure().add_annotation(
                text=f"Ошибка: Колонки {', '.join(missing_cols)} не найдены в данных",
                showarrow=False, xref="paper", yref="paper"
            )
        
        # Конвертируем временные метки
        try:
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
            data = data.sort_values(by=[id_col, timestamp_col])
        except Exception as e:
            logger.warning(f"Ошибка при конвертации временных меток: {e}")
            # Продолжаем, но сортируем хотя бы по ID
            data = data.sort_values(by=id_col)
        
        # Получаем уникальные ID временных рядов
        series_ids = data[id_col].unique()
        
        # Если рядов слишком много, берем только первые max_series
        if len(series_ids) > max_series:
            series_ids = series_ids[:max_series]
        
        # Создаем подграфики - 2 строки (ACF, PACF) и столбцы по количеству рядов
        n_cols = min(len(series_ids), max_series)
        fig = make_subplots(
            rows=2, cols=n_cols,
            subplot_titles=[f"ID: {s}" for s in series_ids[:n_cols]] * 2,
            vertical_spacing=0.1,
            horizontal_spacing=0.05
        )
        
        results = {}
        
        # Для каждого ряда считаем ACF и PACF
        for i, series_id in enumerate(series_ids[:n_cols]):
            # Берем только данные для текущего ряда
            ts_data = data[data[id_col] == series_id][target_col].values
            
            # Если данных мало, пропускаем
            if len(ts_data) <= max_lag:
                logger.warning(f"Ряд {series_id} слишком короткий для анализа автокорреляции")
                continue
                
            # Считаем ACF и PACF
            acf_values = acf(ts_data, nlags=max_lag, fft=True)
            pacf_values = pacf(ts_data, nlags=max_lag)
            
            # Сохраняем результаты
            results[series_id] = {
                'acf': acf_values.tolist(),
                'pacf': pacf_values.tolist()
            }
            
            # Рисуем ACF
            lags = list(range(len(acf_values)))
            fig.add_trace(
                go.Bar(
                    x=lags,
                    y=acf_values,
                    name='ACF',
                    showlegend=True if i == 0 else False
                ),
                row=1, col=i+1
            )
            
            # Добавляем доверительные интервалы для ACF
            confidence = 1.96 / np.sqrt(len(ts_data))
            fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=[confidence] * len(lags),
                    mode='lines',
                    line=dict(dash='dash', color='red', width=1),
                    name='95% CI',
                    showlegend=True if i == 0 else False
                ),
                row=1, col=i+1
            )
            fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=[-confidence] * len(lags),
                    mode='lines',
                    line=dict(dash='dash', color='red', width=1),
                    showlegend=False
                ),
                row=1, col=i+1
            )
            
            # Рисуем PACF
            lags = list(range(len(pacf_values)))
            fig.add_trace(
                go.Bar(
                    x=lags,
                    y=pacf_values,
                    name='PACF',
                    marker_color='green',
                    showlegend=True if i == 0 else False
                ),
                row=2, col=i+1
            )
            
            # Добавляем доверительные интервалы для PACF
            fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=[confidence] * len(lags),
                    mode='lines',
                    line=dict(dash='dash', color='red', width=1),
                    showlegend=False
                ),
                row=2, col=i+1
            )
            fig.add_trace(
                go.Scatter(
                    x=lags,
                    y=[-confidence] * len(lags),
                    mode='lines',
                    line=dict(dash='dash', color='red', width=1),
                    showlegend=False
                ),
                row=2, col=i+1
            )
            
            # Подписи осей
            fig.update_xaxes(title_text='Лаг', row=2, col=i+1)
            if i == 0:
                fig.update_yaxes(title_text='ACF', row=1, col=i+1)
                fig.update_yaxes(title_text='PACF', row=2, col=i+1)
        
        # Настройка графика
        fig.update_layout(
            height=600,
            width=250 * n_cols + 150,
            title=f"Анализ автокорреляции для целевой переменной '{target_col}'",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        )
        
        # Выводим рекомендации для анализа
        recommendations = []
        for series_id, values in results.items():
            acf_vals = values['acf']
            pacf_vals = values['pacf']
            
            # Проверка на основе ACF и PACF
            if abs(acf_vals[1]) > confidence:
                recommendations.append(f"Ряд {series_id}: Значимая автокорреляция порядка 1")
            
            significant_acf = [i+1 for i, v in enumerate(acf_vals[1:], 1) if abs(v) > confidence]
            significant_pacf = [i+1 for i, v in enumerate(pacf_vals[1:], 1) if abs(v) > confidence]
            
            if len(significant_acf) > 0:
                recommendations.append(f"Ряд {series_id}: Значимые ACF лаги: {significant_acf[:5]}")
            
            if len(significant_pacf) > 0:
                recommendations.append(f"Ряд {series_id}: Значимые PACF лаги: {significant_pacf[:5]}")
            
            # Рекомендации по моделям
            if len(significant_acf) > 0 and len(significant_pacf) == 0:
                recommendations.append(f"Ряд {series_id}: Возможно подходит модель MA")
            elif len(significant_acf) == 0 and len(significant_pacf) > 0:
                recommendations.append(f"Ряд {series_id}: Возможно подходит модель AR")
            elif len(significant_acf) > 0 and len(significant_pacf) > 0:
                recommendations.append(f"Ряд {series_id}: Возможно подходит модель ARMA или ARIMA")
        
        return {
            "autocorrelation": results,
            "recommendations": recommendations
        }, fig
        
    except Exception as e:
        logger.error(f"Ошибка при анализе автокорреляции: {e}")
        return {}, go.Figure().add_annotation(
            text=f"Ошибка при анализе автокорреляции: {str(e)}",
            showarrow=False, xref="paper", yref="paper"
        )