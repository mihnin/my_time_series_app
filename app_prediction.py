# app_prediction.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import time
import datetime
import gc
import os
import logging
from pathlib import Path

def run_prediction():
    """
    Функция для выполнения прогнозирования временных рядов с использованием AutoGluon TimeSeries.
    """
    try:
        st.write("Прогнозирование временных рядов с использованием AutoGluon")
        
        # Проверяем наличие данных
        # Вначале проверяем в df_train, затем - в df (для совместимости с app_ui.py)
        if ("df_train" not in st.session_state or st.session_state.get("df_train") is None) and \
           ("df" not in st.session_state or st.session_state.get("df") is None):
            st.warning("Необходимо сначала загрузить данные.")
            return
        
        # Проверяем наличие обученной модели
        if "predictor" not in st.session_state or st.session_state.get("predictor") is None:
            st.error("Необходимо сначала обучить модель.")
            return
        
        # Получаем данные из состояния сессии (из df_train или df)
        if "df_train" in st.session_state and st.session_state.get("df_train") is not None:
            df_train = st.session_state.df_train
        else:
            df_train = st.session_state.df
            # Сохраняем под правильным ключом для совместимости
            st.session_state["df_train"] = df_train
        
        # Получаем предиктор из состояния сессии
        predictor = st.session_state.get("predictor")
        
        # Настраиваем параметры прогнозирования
        st.subheader("Параметры прогнозирования")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Используем сохраненный горизонт прогнозирования, если доступен
            default_horizon = st.session_state.get("prediction_length", 10)
            horizon = st.number_input("Горизонт прогнозирования (периоды)", min_value=1, value=default_horizon)
        
        with col2:
            eval_metric = st.selectbox("Метрика оценки", 
                                      options=["MAE", "MAPE", "RMSE", "MASE"], 
                                      index=0)
            time_limit = st.number_input("Лимит времени обучения (секунды)", 
                                        min_value=60, value=600)
        
        # Выбор моделей
        st.subheader("Выбор моделей")
        use_all_models = st.checkbox("Использовать все доступные модели", value=True)
        
        selected_models = []
        if not use_all_models:
            available_models = [
                "DeepAR", "ARIMA", "AutoARIMA", "AutoETS", "ETS", "Theta", 
                "Prophet", "TemporalFusionTransformer", "PatchTST", "SeasonalNaive"
            ]
            selected_models = st.multiselect("Выберите модели для обучения:", 
                                           options=available_models,
                                           default=["DeepAR", "AutoARIMA"])
        
        # Использование Chronos Bolt
        use_chronos = st.checkbox("Использовать предобученную модель Chronos Bolt", value=True)
        
        # Кнопка для запуска прогнозирования
        if st.button("Запустить прогнозирование"):
            try:
                with st.spinner("Выполняется прогнозирование..."):
                    # Здесь будет код для прогнозирования
                    st.success("Прогнозирование успешно выполнено!")
                    
                    # Имитация результатов (замените на реальный код)
                    results = {
                        "forecast": pd.DataFrame({
                            "date": pd.date_range(start=datetime.datetime.now(), periods=horizon, freq="D"),
                            "value": np.random.randn(horizon).cumsum() + 100
                        }),
                        "best_model": "DeepAR",
                        "metrics": {"MAE": 0.45, "RMSE": 0.67}
                    }
                    
                    # Отображение результатов
                    st.subheader("Результаты прогнозирования")
                    
                    # График прогноза
                    st.write("График прогноза:")
                    fig = px.line(results["forecast"], x="date", y="value")
                    st.plotly_chart(fig)
                    
                    # Метрики модели
                    st.write("Лучшая модель:", results["best_model"])
                    st.write("Метрики:")
                    for metric, value in results["metrics"].items():
                        st.write(f"- {metric}: {value:.4f}")
                
            except Exception as e:
                st.error(f"Ошибка при прогнозировании: {e}")
        else:
            # Если прогноз уже выполнен ранее и результаты есть в кэше, отображаем их
            if "prediction_results" in st.session_state:
                st.info("Отображаются результаты предыдущего прогноза. Нажмите 'Запустить прогнозирование' для обновления.")
                # Здесь можно добавить отображение кэшированных результатов
    
    except Exception as e:
        st.error(f"Ошибка при прогнозировании: {e}")

if __name__ == "__main__":
    # Настройка страницы
    st.set_page_config(page_title="Прогнозирование временных рядов", page_icon="📈", layout="wide")
    st.title("Прогнозирование временных рядов с AutoGluon")
    
    # Запуск основной функции
    run_prediction() 