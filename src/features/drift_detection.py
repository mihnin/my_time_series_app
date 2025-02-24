# src/features/drift_detection.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import logging
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

def detect_concept_drift(historical_df: pd.DataFrame, 
                        new_df: pd.DataFrame,
                        target_col: str,
                        date_col: str,
                        id_col: Optional[str] = None,
                        window_size: int = 30) -> Dict[str, Any]:
    """
    Обнаруживает концепт-дрифт между историческими данными и новыми данными.
    
    Parameters:
    -----------
    historical_df : pandas.DataFrame
        Исторические данные для обучения
    new_df : pandas.DataFrame
        Новые данные для проверки дрифта
    target_col : str
        Название целевой колонки
    date_col : str
        Название колонки с датами
    id_col : str, optional
        Название колонки с идентификаторами
    window_size : int
        Размер окна для скользящих статистик
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с результатами анализа дрифта:
        - drift_detected (bool): обнаружен ли дрифт
        - drift_score (float): оценка силы дрифта (0-1)
        - features_drift (Dict): дрифт по каждому признаку
        - recommendations (List[str]): рекомендации
    """
    result = {
        "drift_detected": False,
        "drift_score": 0.0,
        "statistical_tests": {},
        "features_drift": {},
        "recommendations": []
    }
    
    # Убеждаемся, что колонки дат в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(historical_df[date_col]):
        historical_df = historical_df.copy()
        historical_df[date_col] = pd.to_datetime(historical_df[date_col])
    
    if not pd.api.types.is_datetime64_any_dtype(new_df[date_col]):
        new_df = new_df.copy()
        new_df[date_col] = pd.to_datetime(new_df[date_col])
    
    # Проверяем дрифт в целевой переменной
    try:
        # Тест Колмогорова-Смирнова для проверки различий в распределениях
        target_hist = historical_df[target_col].dropna().values
        target_new = new_df[target_col].dropna().values
        
        if len(target_hist) > 0 and len(target_new) > 0:
            ks_statistic, ks_pvalue = stats.ks_2samp(target_hist, target_new)
            result["statistical_tests"]["ks_test"] = {
                "statistic": float(ks_statistic),
                "p_value": float(ks_pvalue),
                "significant": ks_pvalue < 0.05
            }
            
            if ks_pvalue < 0.05:
                result["drift_detected"] = True
                result["drift_score"] = max(result["drift_score"], ks_statistic)
                result["recommendations"].append(
                    "Обнаружен статистически значимый дрифт в распределении целевой переменной. "
                    "Рекомендуется переобучить модель на новых данных."
                )
        
        # Проверяем изменения в среднем и дисперсии
        mean_hist = historical_df[target_col].mean()
        mean_new = new_df[target_col].mean()
        std_hist = historical_df[target_col].std()
        std_new = new_df[target_col].std()
        
        mean_change_pct = abs(mean_new - mean_hist) / (abs(mean_hist) + 1e-10) * 100
        std_change_pct = abs(std_new - std_hist) / (abs(std_hist) + 1e-10) * 100
        
        result["features_drift"][target_col] = {
            "mean_change_pct": float(mean_change_pct),
            "std_change_pct": float(std_change_pct),
            "significant": mean_change_pct > 20 or std_change_pct > 30
        }
        
        if mean_change_pct > 20:
            result["drift_detected"] = True
            result["drift_score"] = max(result["drift_score"], min(1.0, mean_change_pct / 100))
            result["recommendations"].append(
                f"Среднее значение целевой переменной изменилось на {mean_change_pct:.2f}%. "
                "Рекомендуется переобучить модель."
            )
        
        if std_change_pct > 30:
            result["drift_detected"] = True
            result["drift_score"] = max(result["drift_score"], min(1.0, std_change_pct / 100))
            result["recommendations"].append(
                f"Стандартное отклонение целевой переменной изменилось на {std_change_pct:.2f}%. "
                "Рекомендуется переобучить модель."
            )
    except Exception as e:
        logging.error(f"Ошибка при проверке дрифта целевой переменной: {e}")
    
    # Анализ скользящих средних значений (по времени)
    if id_col:
        # Если есть ID, анализируем дрифт для каждого ID отдельно
        all_ids = set(historical_df[id_col].unique()) & set(new_df[id_col].unique())
        
        for current_id in all_ids:
            hist_id_data = historical_df[historical_df[id_col] == current_id].sort_values(date_col)
            new_id_data = new_df[new_df[id_col] == current_id].sort_values(date_col)
            
            if len(hist_id_data) < window_size or len(new_id_data) < 5:
                continue
            
            # Вычисляем скользящее среднее для исторических данных
            hist_id_data['rolling_mean'] = hist_id_data[target_col].rolling(window=window_size, min_periods=5).mean()
            hist_id_data['rolling_std'] = hist_id_data[target_col].rolling(window=window_size, min_periods=5).std()
            
            # Последнее значение скользящего среднего и стандартного отклонения из исторических данных
            last_hist_mean = hist_id_data['rolling_mean'].iloc[-1]
            last_hist_std = hist_id_data['rolling_std'].iloc[-1]
            
            # Проверяем, насколько новые данные отклоняются от исторических трендов
            new_id_data['mean_diff'] = abs(new_id_data[target_col] - last_hist_mean)
            z_scores = new_id_data['mean_diff'] / (last_hist_std + 1e-10)
            
            # Если среднее значение z-score > 2, это может указывать на дрифт
            mean_z_score = z_scores.mean()
            
            if mean_z_score > 2:
                result["drift_detected"] = True
                drift_intensity = min(1.0, mean_z_score / 5)  # Нормализуем от 0 до 1
                result["drift_score"] = max(result["drift_score"], drift_intensity)
                
                result["recommendations"].append(
                    f"Для ID={current_id} обнаружено значительное отклонение от исторического тренда "
                    f"(средний z-score={mean_z_score:.2f}). "
                    "Рекомендуется переобучить модель на новых данных."
                )
    else:
        # Если нет ID, анализируем данные как единый временной ряд
        hist_data = historical_df.sort_values(date_col)
        new_data = new_df.sort_values(date_col)
        
        if len(hist_data) >= window_size and len(new_data) >= 5:
            # Вычисляем скользящее среднее для исторических данных
            hist_data['rolling_mean'] = hist_data[target_col].rolling(window=window_size, min_periods=5).mean()
            hist_data['rolling_std'] = hist_data[target_col].rolling(window=window_size, min_periods=5).std()
            
            # Последнее значение скользящего среднего и стандартного отклонения из исторических данных
            last_hist_mean = hist_data['rolling_mean'].iloc[-1]
            last_hist_std = hist_data['rolling_std'].iloc[-1]
            
            # Проверяем, насколько новые данные отклоняются от исторических трендов
            new_data['mean_diff'] = abs(new_data[target_col] - last_hist_mean)
            z_scores = new_data['mean_diff'] / (last_hist_std + 1e-10)
            
            # Если среднее значение z-score > 2, это может указывать на дрифт
            mean_z_score = z_scores.mean()
            
            if mean_z_score > 2:
                result["drift_detected"] = True
                drift_intensity = min(1.0, mean_z_score / 5)  # Нормализуем от 0 до 1
                result["drift_score"] = max(result["drift_score"], drift_intensity)
                
                result["recommendations"].append(
                    f"Обнаружено значительное отклонение от исторического тренда "
                    f"(средний z-score={mean_z_score:.2f}). "
                    "Рекомендуется переобучить модель на новых данных."
                )
    
    # Добавляем графики для визуализации дрифта
    result["figures"] = create_drift_visualizations(historical_df, new_df, target_col, date_col, id_col)
    
    return result

def create_drift_visualizations(historical_df: pd.DataFrame, 
                              new_df: pd.DataFrame,
                              target_col: str,
                              date_col: str,
                              id_col: Optional[str] = None) -> Dict[str, Any]:
    """
    Создает визуализации для анализа дрифта данных.
    
    Returns:
    --------
    Dict[str, Any]
        Словарь с графиками для визуализации дрифта
    """
    figures = {}
    
    # Убеждаемся, что колонки дат в формате datetime
    if not pd.api.types.is_datetime64_any_dtype(historical_df[date_col]):
        historical_df = historical_df.copy()
        historical_df[date_col] = pd.to_datetime(historical_df[date_col])
    
    if not pd.api.types.is_datetime64_any_dtype(new_df[date_col]):
        new_df = new_df.copy()
        new_df[date_col] = pd.to_datetime(new_df[date_col])
    
    # Добавляем метку источника данных
    hist_df = historical_df.copy()
    hist_df['source'] = 'Исторические'
    
    new_df_copy = new_df.copy()
    new_df_copy['source'] = 'Новые'
    
    # Объединяем для сравнения
    combined_df = pd.concat([hist_df, new_df_copy])
    
    # 1. Распределение целевой переменной
    fig_dist = px.histogram(combined_df, x=target_col, color='source', 
                           barmode='overlay', nbins=50,
                           title='Сравнение распределения целевой переменной')
    figures['distribution'] = fig_dist
    
    # 2. Временные ряды
    if id_col and combined_df[id_col].nunique() > 1:
        # Ограничиваем до 5 наиболее представленных ID
        top_ids = combined_df.groupby(id_col).size().nlargest(5).index.tolist()
        plot_df = combined_df[combined_df[id_col].isin(top_ids)]
        
        fig_time = px.line(plot_df, x=date_col, y=target_col, 
                         color=id_col, line_dash='source',
                         title='Сравнение временных рядов (топ-5 ID)')
    else:
        fig_time = px.line(combined_df, x=date_col, y=target_col, 
                         color='source',
                         title='Сравнение временных рядов')
    
    figures['time_series'] = fig_time
    
    # 3. Boxplots для сравнения
    fig_box = px.box(combined_df, x='source', y=target_col,
                    title='Boxplot сравнение целевой переменной')
    figures['boxplot'] = fig_box
    
    # 4. Scatter plot средних значений по времени (для визуализации трендов)
    if id_col:
        hist_means = hist_df.groupby([pd.Grouper(key=date_col, freq='M')])[target_col].mean().reset_index()
        hist_means['source'] = 'Исторические'
        
        new_means = new_df_copy.groupby([pd.Grouper(key=date_col, freq='M')])[target_col].mean().reset_index()
        new_means['source'] = 'Новые'
        
        combined_means = pd.concat([hist_means, new_means])
        
        fig_trend = px.line(combined_means, x=date_col, y=target_col, color='source',
                           title='Тренды средних месячных значений')
        figures['trend'] = fig_trend
    
    return figures

def display_drift_results(drift_results: Dict[str, Any]):
    """
    Отображает результаты анализа дрифта в Streamlit.
    """
    import streamlit as st
    
    if drift_results["drift_detected"]:
        st.error(f"⚠️ Обнаружен концепт-дрифт (оценка: {drift_results['drift_score']:.2f})")
        
        # Отображаем рекомендации
        st.subheader("Рекомендации")
        for recommendation in drift_results["recommendations"]:
            st.warning(f"- {recommendation}")
    else:
        st.success("✅ Концепт-дрифт не обнаружен, модель актуальна")
    
    # Отображаем графики
    if "figures" in drift_results:
        st.subheader("Визуализация дрифта")
        
        if "distribution" in drift_results["figures"]:
            st.plotly_chart(drift_results["figures"]["distribution"], use_container_width=True)
        
        if "boxplot" in drift_results["figures"]:
            st.plotly_chart(drift_results["figures"]["boxplot"], use_container_width=True)
        
        if "time_series" in drift_results["figures"]:
            st.plotly_chart(drift_results["figures"]["time_series"], use_container_width=True)
        
        if "trend" in drift_results["figures"]:
            st.plotly_chart(drift_results["figures"]["trend"], use_container_width=True)
    
    # Отображаем статистические тесты
    if "statistical_tests" in drift_results and drift_results["statistical_tests"]:
        st.subheader("Статистические тесты")
        
        for test_name, test_results in drift_results["statistical_tests"].items():
            if test_name == "ks_test":
                st.write(f"Тест Колмогорова-Смирнова:")
                st.write(f"- Статистика: {test_results['statistic']:.4f}")
                st.write(f"- p-значение: {test_results['p_value']:.4f}")
                
                if test_results['significant']:
                    st.write("- Результат: Распределения статистически значимо различаются (p < 0.05)")
                else:
                    st.write("- Результат: Различия статистически не значимы (p >= 0.05)")
    
    # Отображаем дрифт по признакам
    if "features_drift" in drift_results and drift_results["features_drift"]:
        st.subheader("Изменения в статистиках целевой переменной")
        
        for feature, drift_info in drift_results["features_drift"].items():
            st.write(f"**{feature}**:")
            st.write(f"- Изменение среднего: {drift_info['mean_change_pct']:.2f}%")
            st.write(f"- Изменение станд. отклонения: {drift_info['std_change_pct']:.2f}%")