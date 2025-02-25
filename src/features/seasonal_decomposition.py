# src/features/seasonal_decomposition.py
import pandas as pd
import numpy as np
import logging
import streamlit as st
from typing import Dict, List, Tuple, Any, Optional
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def decompose_time_series(df: pd.DataFrame, 
                         date_col: str, 
                         target_col: str, 
                         id_col: Optional[str] = None,
                         period: Optional[int] = None) -> Dict[str, Any]:
    """
    Выполняет декомпозицию временного ряда на тренд, сезонность и остатки.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм с данными
    date_col : str
        Название колонки с датами
    target_col : str
        Название целевой колонки
    id_col : str, optional
        Название колонки с идентификаторами
    period : int, optional
        Период сезонности (например, 12 для месячных данных с годовой сезонностью)
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с результатами декомпозиции:
        - decomposition (Dict): компоненты декомпозиции
        - figures (Dict): графики
        - recommendations (List[str]): рекомендации
    """
    from statsmodels.tsa.seasonal import seasonal_decompose
    import statsmodels.api as sm
    
    result = {
        "decomposition": {},
        "figures": {},
        "recommendations": []
    }
    
    # Убеждаемся, что колонка даты в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
    
    # Определяем частоту данных, если не указан период
    if period is None:
        try:
            # Сортируем по дате
            sorted_df = df.sort_values(date_col)
            
            # Вычисляем разницу между соседними датами
            date_diffs = sorted_df[date_col].diff()
            most_common_diff = date_diffs.mode()[0]
            
            # Определяем типичный интервал
            if most_common_diff.days == 1:
                # Ежедневные данные
                period = 7  # Недельная сезонность
                result["recommendations"].append(
                    "Автоматически определены ежедневные данные. Используется недельная сезонность (period=7)."
                )
            elif most_common_diff.days >= 28 and most_common_diff.days <= 31:
                # Ежемесячные данные
                period = 12  # Годовая сезонность
                result["recommendations"].append(
                    "Автоматически определены ежемесячные данные. Используется годовая сезонность (period=12)."
                )
            elif most_common_diff.days >= 7 and most_common_diff.days <= 7:
                # Еженедельные данные
                period = 52  # Годовая сезонность
                result["recommendations"].append(
                    "Автоматически определены еженедельные данные. Используется годовая сезонность (period=52)."
                )
            else:
                # По умолчанию
                period = 12
                result["recommendations"].append(
                    f"Не удалось точно определить сезонность. Используется значение по умолчанию (period={period})."
                )
        except Exception as e:
            period = 12  # Значение по умолчанию
            logging.warning(f"Ошибка при определении периода: {e}")
            result["recommendations"].append(
                f"Произошла ошибка при определении периода: {e}. "
                f"Используется значение по умолчанию (period={period})."
            )
    
    # Если указан ID, выполняем декомпозицию для каждого ID отдельно
    if id_col and id_col in df.columns:
        unique_ids = df[id_col].unique()
        
        if len(unique_ids) > 5:
            # Ограничиваем количество рядов для декомпозиции
            result["recommendations"].append(
                f"Слишком много уникальных ID ({len(unique_ids)}). "
                "Выполняется декомпозиция только для 5 наиболее длинных рядов."
            )
            
            # Выбираем 5 ID с наибольшим количеством точек
            id_counts = df.groupby(id_col).size()
            top_ids = id_counts.nlargest(5).index.tolist()
            unique_ids = top_ids
        
        for current_id in unique_ids:
            subset = df[df[id_col] == current_id].copy()
            
            # Сортируем по дате и проверяем, что достаточно точек
            subset = subset.sort_values(date_col)
            
            if len(subset) < 2 * period:
                result["recommendations"].append(
                    f"Для ID={current_id} недостаточно точек для декомпозиции "
                    f"(требуется минимум {2 * period}, имеется {len(subset)})."
                )
                continue
            
            try:
                # Выполняем декомпозицию
                decomposition = seasonal_decompose(
                    subset[target_col].values, 
                    model='additive', 
                    period=period
                )
                
                # Сохраняем результаты
                result["decomposition"][str(current_id)] = {
                    "trend": decomposition.trend,
                    "seasonal": decomposition.seasonal,
                    "resid": decomposition.resid,
                    "observed": decomposition.observed
                }
                
                # Создаем график декомпозиции
                dates = subset[date_col].values
                
                fig = make_subplots(
                    rows=4, cols=1,
                    subplot_titles=("Observed", "Trend", "Seasonal", "Residual"),
                    vertical_spacing=0.1
                )
                
                # Убираем NaN значения
                valid_indices = ~np.isnan(decomposition.trend)
                valid_dates = dates[valid_indices]
                
                fig.add_trace(
                    go.Scatter(x=valid_dates, y=decomposition.observed[valid_indices], name="Observed"),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=valid_dates, y=decomposition.trend[valid_indices], name="Trend"),
                    row=2, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=valid_dates, y=decomposition.seasonal[valid_indices], name="Seasonal"),
                    row=3, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=valid_dates, y=decomposition.resid[valid_indices], name="Residual"),
                    row=4, col=1
                )
                
                fig.update_layout(
                    height=800,
                    title_text=f"Декомпозиция временного ряда для ID={current_id}",
                    showlegend=False
                )
                
                result["figures"][str(current_id)] = fig
                
                # Анализируем сезонность
                seasonal_strength = 1 - np.var(decomposition.resid[valid_indices]) / np.var(decomposition.observed[valid_indices] - decomposition.trend[valid_indices])
                
                if seasonal_strength > 0.6:
                    result["recommendations"].append(
                        f"Для ID={current_id} обнаружена сильная сезонность (strength={seasonal_strength:.2f}). "
                        "Рекомендуется использовать модели, учитывающие сезонность."
                    )
                elif seasonal_strength > 0.3:
                    result["recommendations"].append(
                        f"Для ID={current_id} обнаружена умеренная сезонность (strength={seasonal_strength:.2f})."
                    )
                else:
                    result["recommendations"].append(
                        f"Для ID={current_id} сезонность слабо выражена (strength={seasonal_strength:.2f})."
                    )
                
            except Exception as e:
                logging.error(f"Ошибка при декомпозиции для ID={current_id}: {e}")
                result["recommendations"].append(
                    f"Не удалось выполнить декомпозицию для ID={current_id}: {e}"
                )
    else:
        # Выполняем декомпозицию для всего ряда
        try:
            # Сортируем по дате
            sorted_df = df.sort_values(date_col)
            
            if len(sorted_df) < 2 * period:
                result["recommendations"].append(
                    f"Недостаточно точек для декомпозиции "
                    f"(требуется минимум {2 * period}, имеется {len(sorted_df)})."
                )
                return result
            
            # Выполняем декомпозицию
            decomposition = seasonal_decompose(
                sorted_df[target_col].values, 
                model='additive', 
                period=period
            )
            
            # Сохраняем результаты
            result["decomposition"]["all"] = {
                "trend": decomposition.trend,
                "seasonal": decomposition.seasonal,
                "resid": decomposition.resid,
                "observed": decomposition.observed
            }
            
            # Создаем график декомпозиции
            dates = sorted_df[date_col].values
            
            fig = make_subplots(
                rows=4, cols=1,
                subplot_titles=("Observed", "Trend", "Seasonal", "Residual"),
                vertical_spacing=0.1
            )
            
            # Убираем NaN значения
            valid_indices = ~np.isnan(decomposition.trend)
            valid_dates = dates[valid_indices]
            
            fig.add_trace(
                go.Scatter(x=valid_dates, y=decomposition.observed[valid_indices], name="Observed"),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=valid_dates, y=decomposition.trend[valid_indices], name="Trend"),
                row=2, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=valid_dates, y=decomposition.seasonal[valid_indices], name="Seasonal"),
                row=3, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=valid_dates, y=decomposition.resid[valid_indices], name="Residual"),
                row=4, col=1
            )
            
            fig.update_layout(
                height=800,
                title_text="Декомпозиция временного ряда",
                showlegend=False
            )
            
            result["figures"]["all"] = fig
            
            # Анализируем сезонность
            seasonal_strength = 1 - np.var(decomposition.resid[valid_indices]) / np.var(decomposition.observed[valid_indices] - decomposition.trend[valid_indices])
            
            if seasonal_strength > 0.6:
                result["recommendations"].append(
                    f"Обнаружена сильная сезонность (strength={seasonal_strength:.2f}). "
                    "Рекомендуется использовать модели, учитывающие сезонность."
                )
            elif seasonal_strength > 0.3:
                result["recommendations"].append(
                    f"Обнаружена умеренная сезонность (strength={seasonal_strength:.2f})."
                )
            else:
                result["recommendations"].append(
                    f"Сезонность слабо выражена (strength={seasonal_strength:.2f})."
                )
            
        except Exception as e:
            logging.error(f"Ошибка при декомпозиции: {e}")
            result["recommendations"].append(
                f"Не удалось выполнить декомпозицию: {e}"
            )
    
    return result

def display_decomposition_results(decomposition_results: Dict[str, Any]):
    """
    Отображает результаты декомпозиции в Streamlit.
    """
    import streamlit as st
    
    st.subheader("Декомпозиция временного ряда")
    
    if decomposition_results["recommendations"]:
        with st.expander("Рекомендации", expanded=True):
            for recommendation in decomposition_results["recommendations"]:
                st.info(f"- {recommendation}")
    
    # Отображаем графики
    if "figures" in decomposition_results:
        for id_val, fig in decomposition_results["figures"].items():
            if id_val == "all":
                st.write("### Декомпозиция для всего ряда")
            else:
                st.write(f"### Декомпозиция для ID={id_val}")
            
            st.plotly_chart(fig, use_container_width=True)