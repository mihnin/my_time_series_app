# src/features/correlation_analysis.py
import pandas as pd
import numpy as np
import logging
import streamlit as st
from typing import List, Dict, Tuple, Any, Optional
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

def analyze_correlations(df: pd.DataFrame, static_features: List[str], 
                        target_col: str) -> Dict[str, Any]:
    """
    Анализирует корреляции между статическими признаками и целевой переменной.
    
    Parameters:
    -----------
    df : pandas.DataFrame
        Датафрейм с данными
    static_features : List[str]
        Список статических признаков
    target_col : str
        Название целевой колонки
        
    Returns:
    --------
    Dict[str, Any]
        Словарь с результатами анализа корреляций:
        - correlation_matrix (pd.DataFrame): матрица корреляций
        - target_correlations (pd.Series): корреляции с целевой переменной
        - multicollinearity (Dict): информация о мультиколлинеарности
        - recommendations (List[str]): рекомендации
        - figures (Dict): графики
    """
    result = {
        "correlation_matrix": None,
        "target_correlations": None,
        "multicollinearity": {},
        "recommendations": [],
        "figures": {}
    }
    
    # Отбираем только числовые колонки для корреляционного анализа
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Собираем все статические признаки, которые есть в датафрейме и являются числовыми
    features_to_analyze = [col for col in static_features if col in numeric_cols]
    
    # Добавляем целевую переменную, если она числовая
    if target_col in numeric_cols:
        features_to_analyze.append(target_col)
    
    if len(features_to_analyze) <= 1:
        result["recommendations"].append(
            "Недостаточно числовых признаков для корреляционного анализа."
        )
        return result
    
    # Создаем матрицу корреляций
    try:
        correlation_matrix = df[features_to_analyze].corr(method='pearson')
        result["correlation_matrix"] = correlation_matrix
        
        # Сохраняем корреляции с целевой переменной
        if target_col in correlation_matrix.columns:
            target_correlations = correlation_matrix[target_col].drop(target_col)
            result["target_correlations"] = target_correlations
            
            # Создаем график корреляций с целевой переменной
            fig_target_corr = px.bar(
                x=target_correlations.index,
                y=target_correlations.values,
                title='Корреляция признаков с целевой переменной',
                labels={'x': 'Признак', 'y': 'Корреляция Пирсона'}
            )
            result["figures"]["target_correlations"] = fig_target_corr
            
            # Рекомендации на основе корреляций с целевой переменной
            strong_correlations = target_correlations[abs(target_correlations) > 0.7]
            if not strong_correlations.empty:
                strong_features = strong_correlations.index.tolist()
                result["recommendations"].append(
                    f"Признаки с сильной корреляцией с целевой переменной ({', '.join(strong_features)}) "
                    "могут быть особенно полезны для модели."
                )
            
            weak_correlations = target_correlations[abs(target_correlations) < 0.1]
            if not weak_correlations.empty:
                weak_features = weak_correlations.index.tolist()
                result["recommendations"].append(
                    f"Признаки со слабой корреляцией с целевой переменной ({', '.join(weak_features)}) "
                    "могут быть менее информативными."
                )
        
        # Анализ мультиколлинеарности
        if len(features_to_analyze) > 2:
            # Убираем целевую переменную из анализа мультиколлинеарности
            features_without_target = [f for f in features_to_analyze if f != target_col]
            
            if len(features_without_target) > 1:
                feature_correlations = correlation_matrix.loc[features_without_target, features_without_target]
                
                # Находим пары признаков с высокой корреляцией
                high_correlation_pairs = []
                for i in range(len(features_without_target)):
                    for j in range(i+1, len(features_without_target)):
                        feat1 = features_without_target[i]
                        feat2 = features_without_target[j]
                        correlation = feature_correlations.loc[feat1, feat2]
                        
                        if abs(correlation) > 0.7:
                            high_correlation_pairs.append({
                                "feature1": feat1,
                                "feature2": feat2,
                                "correlation": correlation
                            })
                
                result["multicollinearity"]["high_correlation_pairs"] = high_correlation_pairs
                
                if high_correlation_pairs:
                    pairs_str = ", ".join([f"{p['feature1']} и {p['feature2']} ({p['correlation']:.2f})" 
                                         for p in high_correlation_pairs])
                    result["recommendations"].append(
                        f"Обнаружена мультиколлинеарность между признаками: {pairs_str}. "
                        "Рекомендуется использовать только один признак из каждой пары."
                    )
                
                # Создаем тепловую карту корреляций
                fig_heatmap = px.imshow(
                    feature_correlations,
                    text_auto=True,
                    title='Тепловая карта корреляций признаков',
                    color_continuous_scale='RdBu_r',
                    zmin=-1, zmax=1
                )
                result["figures"]["correlation_heatmap"] = fig_heatmap
        
        # Вычисляем VIF (Variance Inflation Factor) для обнаружения мультиколлинеарности
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
            
            features_without_target = [f for f in features_to_analyze if f != target_col]
            if len(features_without_target) > 1:
                X = df[features_without_target].dropna()
                
                if X.shape[0] > 0:
                    # Добавляем константу для интерсепта
                    X = pd.DataFrame({col: X[col] for col in features_without_target})
                    X = X.assign(const=1)
                    
                    # Вычисляем VIF
                    vif_data = pd.DataFrame()
                    vif_data["feature"] = features_without_target
                    vif_data["VIF"] = [variance_inflation_factor(X.values, i) 
                                     for i in range(len(features_without_target))]
                    
                    result["multicollinearity"]["vif"] = vif_data
                    
                    # Признаки с VIF > 5 могут иметь мультиколлинеарность
                    high_vif_features = vif_data[vif_data["VIF"] > 5]
                    if not high_vif_features.empty:
                        features_str = ", ".join([f"{row['feature']} (VIF={row['VIF']:.2f})" 
                                               for _, row in high_vif_features.iterrows()])
                        result["recommendations"].append(
                            f"По фактору инфляции дисперсии (VIF) следующие признаки "
                            f"имеют мультиколлинеарность: {features_str}."
                        )
                    
                    # Создаем график VIF
                    fig_vif = px.bar(
                        vif_data, x='feature', y='VIF',
                        title='Фактор инфляции дисперсии (VIF) признаков',
                        labels={'feature': 'Признак', 'VIF': 'VIF'}
                    )
                    # Добавляем горизонтальную линию на уровне VIF=5
                    fig_vif.add_shape(
                        type="line", line=dict(dash='dash', color='red'),
                        y0=5, y1=5, x0=-0.5, x1=len(features_without_target)-0.5
                    )
                    result["figures"]["vif"] = fig_vif
        except Exception as e:
            logging.warning(f"Не удалось вычислить VIF: {e}")
                
    except Exception as e:
        logging.error(f"Ошибка при анализе корреляций: {e}")
        result["recommendations"].append(f"Не удалось выполнить корреляционный анализ: {e}")
    
    return result

def display_correlation_results(correlation_results: Dict[str, Any]):
    """
    Отображает результаты корреляционного анализа в Streamlit.
    """
    import streamlit as st
    
    st.subheader("Анализ корреляций и мультиколлинеарности")
    
    if correlation_results["recommendations"]:
        with st.expander("Рекомендации по признакам", expanded=True):
            for recommendation in correlation_results["recommendations"]:
                st.info(f"- {recommendation}")
    
    # Отображаем графики
    if "figures" in correlation_results:
        if "target_correlations" in correlation_results["figures"]:
            st.plotly_chart(correlation_results["figures"]["target_correlations"], use_container_width=True)
        
        if "correlation_heatmap" in correlation_results["figures"]:
            st.plotly_chart(correlation_results["figures"]["correlation_heatmap"], use_container_width=True)
        
        if "vif" in correlation_results["figures"]:
            st.plotly_chart(correlation_results["figures"]["vif"], use_container_width=True)
    
    # Показываем таблицу с VIF, если есть
    if "multicollinearity" in correlation_results and "vif" in correlation_results["multicollinearity"]:
        st.subheader("Фактор инфляции дисперсии (VIF)")
        st.write("VIF > 5 указывает на возможную мультиколлинеарность")
        st.write("VIF > 10 указывает на сильную мультиколлинеарность")
        
        vif_data = correlation_results["multicollinearity"]["vif"]
        
        # Добавляем цветовое форматирование
        def highlight_vif(val):
            color = 'white'
            if val > 10:
                color = 'red'
            elif val > 5:
                color = 'orange'
            return f'background-color: {color}'
        
        # Отображаем с форматированием
        st.dataframe(vif_data.style.applymap(highlight_vif, subset=['VIF']))
    
    # Показываем пары с высокой корреляцией, если есть
    if ("multicollinearity" in correlation_results and 
        "high_correlation_pairs" in correlation_results["multicollinearity"] and
        correlation_results["multicollinearity"]["high_correlation_pairs"]):
        
        st.subheader("Пары признаков с высокой корреляцией")
        
        pairs = correlation_results["multicollinearity"]["high_correlation_pairs"]
        pairs_df = pd.DataFrame(pairs)
        
        # Добавляем цветовое форматирование
        def highlight_correlation(val):
            color = 'white'
            if abs(val) > 0.9:
                color = 'red'
            elif abs(val) > 0.7:
                color = 'orange'
            return f'background-color: {color}'
        
        # Отображаем с форматированием
        st.dataframe(pairs_df.style.applymap(highlight_correlation, subset=['correlation']))