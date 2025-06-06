# src/validation/data_validation.py
import pandas as pd
import logging
import streamlit as st
from typing import Dict, Any, Optional
import plotly.express as px
import plotly.graph_objects as go
import time
import gc
from collections import Counter

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

def display_validation_results(validation_results: Dict[str, Any]):
    """
    Отображает результаты валидации в Streamlit.
    """
    if not validation_results["is_valid"]:
        st.error("⚠️ Обнаружены критические проблемы с данными:")
        for error in validation_results["errors"]:
            st.error(f"- {error}")
        return False
    
    st.success("✅ Данные прошли базовую валидацию.")
    
    if validation_results["warnings"]:
        st.warning("⚠️ Обнаружены потенциальные проблемы:")
        for warning in validation_results["warnings"]:
            st.warning(f"- {warning}")
    
    stats = validation_results["stats"]
    
    # Отображаем основные статистики
    st.subheader("Статистики данных")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Количество строк", stats["rows_count"])
        if "unique_ids" in stats:
            st.metric("Уникальных ID", stats["unique_ids"])
    
    with col2:
        if stats["target_mean"] is not None:
            st.metric("Среднее значение", f"{stats['target_mean']:.2f}")
        if stats["target_median"] is not None:
            st.metric("Медиана", f"{stats['target_median']:.2f}")
    
    with col3:
        if stats["target_min"] is not None:
            st.metric("Минимум", f"{stats['target_min']:.2f}")
        if stats["target_max"] is not None:
            st.metric("Максимум", f"{stats['target_max']:.2f}")
    
    # Круговая диаграмма пропусков
    if stats["missing_values"]["dt_col"] > 0 or stats["missing_values"]["tgt_col"] > 0:
        st.subheader("Пропущенные значения")
        missing_data = {
            "Дата": stats["missing_values"]["dt_col"],
            "Целевая переменная": stats["missing_values"]["tgt_col"],
            "Полные записи": stats["rows_count"] - max(stats["missing_values"]["dt_col"], 
                                                     stats["missing_values"]["tgt_col"])
        }
        fig = px.pie(values=list(missing_data.values()), 
                    names=list(missing_data.keys()),
                    title="Распределение пропусков")
        st.plotly_chart(fig, use_container_width=True)
    
    return True

def plot_target_distribution(df: pd.DataFrame, tgt_col: str, title: str = "Распределение целевой переменной"):
    """
    Создает график распределения целевой переменной.
    """
    if tgt_col not in df.columns or not pd.api.types.is_numeric_dtype(df[tgt_col]):
        return None
    
    fig = px.histogram(df, x=tgt_col, nbins=50, title=title)
    fig.update_layout(showlegend=False)
    return fig

def plot_target_boxplot(df: pd.DataFrame, tgt_col: str, id_col: Optional[str] = None, 
                        title: str = "Диаграмма размаха целевой переменной"):
    """
    Создает боксплот целевой переменной, сгруппированный по ID (если указан).
    """
    if tgt_col not in df.columns or not pd.api.types.is_numeric_dtype(df[tgt_col]):
        return None
    
    if id_col and id_col in df.columns and df[id_col].nunique() <= 10:  # Ограничиваем количество групп для читаемости
        fig = px.box(df, x=id_col, y=tgt_col, title=title)
    else:
        fig = px.box(df, y=tgt_col, title=title)
    
    return fig

def plot_target_time_series(df: pd.DataFrame, dt_col: str, tgt_col: str, id_col: Optional[str] = None,
                          title: str = "Временной ряд целевой переменной"):
    """
    Создает график временного ряда целевой переменной.
    """
    if dt_col not in df.columns or tgt_col not in df.columns or not pd.api.types.is_numeric_dtype(df[tgt_col]):
        return None
    
    # Убеждаемся, что колонка даты в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
        df = df.copy()
        df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
    
    if id_col and id_col in df.columns and df[id_col].nunique() > 1:
        # Ограничиваем количество ID для читаемости
        top_ids = df.groupby(id_col)[tgt_col].count().nlargest(5).index.tolist()
        plot_df = df[df[id_col].isin(top_ids)].copy()
        fig = px.line(plot_df, x=dt_col, y=tgt_col, color=id_col, 
                     title=f"{title} (топ-5 по количеству точек)")
    else:
        fig = px.line(df, x=dt_col, y=tgt_col, title=title)
    
    return fig

def analyze_seasonal_patterns(df: pd.DataFrame, dt_col: str, tgt_col: str, id_col: Optional[str] = None):
    """
    Анализирует сезонные паттерны во временном ряде.
    """
    if dt_col not in df.columns or tgt_col not in df.columns or not pd.api.types.is_numeric_dtype(df[tgt_col]):
        return {"error": "Некорректные колонки даты или целевой переменной"}
    
    results = {}
    
    # Убеждаемся, что колонка даты в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
        df = df.copy()
        df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
    
    # Добавляем временные компоненты
    df_analysis = df.copy()
    df_analysis['year'] = df_analysis[dt_col].dt.year
    df_analysis['month'] = df_analysis[dt_col].dt.month
    df_analysis['day'] = df_analysis[dt_col].dt.day
    df_analysis['dayofweek'] = df_analysis[dt_col].dt.dayofweek
    df_analysis['quarter'] = df_analysis[dt_col].dt.quarter
    
    # Анализ по месяцам
    try:
        monthly_pattern = df_analysis.groupby('month')[tgt_col].agg(['mean', 'median', 'std']).reset_index()
        results['monthly'] = monthly_pattern
        
        # Анализ по дням недели
        weekday_pattern = df_analysis.groupby('dayofweek')[tgt_col].agg(['mean', 'median', 'std']).reset_index()
        weekday_pattern['dayofweek'] = weekday_pattern['dayofweek'].map({
            0: 'Понедельник', 1: 'Вторник', 2: 'Среда', 3: 'Четверг', 
            4: 'Пятница', 5: 'Суббота', 6: 'Воскресенье'
        })
        results['weekday'] = weekday_pattern
        
        # Анализ по кварталам
        quarterly_pattern = df_analysis.groupby('quarter')[tgt_col].agg(['mean', 'median', 'std']).reset_index()
        results['quarterly'] = quarterly_pattern
        
        # Графики
        fig_monthly = px.bar(monthly_pattern, x='month', y='mean', 
                            error_y='std', title='Сезонность по месяцам')
        fig_monthly.update_xaxes(tickvals=list(range(1, 13)), 
                                ticktext=['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 
                                        'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'])
        
        fig_weekday = px.bar(weekday_pattern, x='dayofweek', y='mean', 
                            error_y='std', title='Сезонность по дням недели')
        
        fig_quarterly = px.bar(quarterly_pattern, x='quarter', y='mean', 
                            error_y='std', title='Сезонность по кварталам')
        
        results['figures'] = {
            'monthly': fig_monthly,
            'weekday': fig_weekday,
            'quarterly': fig_quarterly
        }
    except Exception as e:
        results["error"] = f"Ошибка при анализе сезонности: {e}"
    
    return results

def detect_autocorrelation(df: pd.DataFrame, dt_col: str, tgt_col: str, id_col: Optional[str] = None, 
                          max_lag: int = 30):
    """
    Вычисляет и визуализирует автокорреляцию временного ряда.
    """
    if dt_col not in df.columns or tgt_col not in df.columns or not pd.api.types.is_numeric_dtype(df[tgt_col]):
        return {"error": "Некорректные колонки даты или целевой переменной"}
    
    try:
        from statsmodels.tsa.stattools import acf, pacf
    except ImportError:
        return {"error": "Для анализа автокорреляции требуется библиотека statsmodels"}
    
    results = {}
    
    # Убеждаемся, что колонка даты в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(df[dt_col]):
        df = df.copy()
        df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
    
    try:
        if id_col and id_col in df.columns and df[id_col].nunique() > 1:
            # Выбираем самый длинный временной ряд для анализа
            id_counts = df.groupby(id_col).size()
            top_id = id_counts.idxmax()
            time_series = df[df[id_col] == top_id].sort_values(dt_col)[tgt_col].values
            results['analyzed_id'] = top_id
        else:
            time_series = df.sort_values(dt_col)[tgt_col].values
        
        # Вычисляем ACF и PACF
        acf_values = acf(time_series, nlags=min(max_lag, len(time_series) - 1), fft=True)
        pacf_values = pacf(time_series, nlags=min(max_lag, len(time_series) - 1))
        
        # Создаем графики
        fig_acf = go.Figure()
        fig_acf.add_trace(go.Bar(x=list(range(len(acf_values))), y=acf_values))
        fig_acf.update_layout(title='Автокорреляционная функция (ACF)',
                            xaxis_title='Лаг',
                            yaxis_title='ACF')
        
        fig_pacf = go.Figure()
        fig_pacf.add_trace(go.Bar(x=list(range(len(pacf_values))), y=pacf_values))
        fig_pacf.update_layout(title='Частичная автокорреляционная функция (PACF)',
                            xaxis_title='Лаг',
                            yaxis_title='PACF')
        
        results['acf'] = acf_values.tolist()
        results['pacf'] = pacf_values.tolist()
        results['figures'] = {
            'acf': fig_acf,
            'pacf': fig_pacf
        }
    except Exception as e:
        logging.error(f"Ошибка при вычислении автокорреляции: {e}")
        results['error'] = str(e)
    
    return results