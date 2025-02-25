# data_analysis.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
import time
import io

from src.validation.data_validation import (
    validate_dataset, display_validation_results,
    plot_target_distribution, plot_target_boxplot, plot_target_time_series,
    analyze_seasonal_patterns, detect_autocorrelation
)
from src.features.correlation_analysis import (
    analyze_correlations, display_correlation_results
)
from src.features.seasonal_decomposition import (
    decompose_time_series, display_decomposition_results
)
from src.features.drift_detection import (
    detect_concept_drift, display_drift_results
)
from src.data.data_processing import (
    load_data, show_dataset_stats, split_train_test, detect_outliers
)
from src.features.feature_engineering import (
    add_time_features, apply_target_transformations,
    generate_lag_features, generate_rolling_features
)

# Вспомогательная функция для выгрузки данных в Excel
def download_excel(df, filename="data_export.xlsx"):
    """Создает кнопку для выгрузки данных в Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    
    processed_data = output.getvalue()
    
    st.download_button(
        label="📥 Выгрузить в Excel",
        data=processed_data,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Функция для отображения информации о применении данных
def show_data_usage_info(feature_type):
    """Показывает информацию о том, как использовать данные"""
    st.info(f"""
    ### Как использовать {feature_type}?
    
    - **Для анализа**: Сгенерированные данные применяются к текущей сессии анализа и не влияют на основной датасет. 
      С ними можно проводить дальнейший анализ, строить графики и исследовать взаимосвязи.
    
    - **Для обучения моделей**: Вы можете использовать кнопку "Использовать на главной странице" для передачи этих данных 
      на основную страницу для обучения моделей.
    
    - **Для экспорта**: С помощью кнопки "Выгрузить в Excel" вы можете скачать данные для использования в других 
      инструментах аналитики или сохранения результатов.
    """)

def run_data_analysis():
    """
    Страница расширенного анализа данных с возможностью загрузки данных
    непосредственно на странице.
    """
    st.title("Расширенный анализ данных")
    
    # Раздел для загрузки данных
    st.header("1. Загрузка данных")
    
    # Инициализируем session_state переменные для анализа данных если их нет
    if "df_analysis" not in st.session_state:
        st.session_state["df_analysis"] = None
    
    if "analysis_dt_col" not in st.session_state:
        st.session_state["analysis_dt_col"] = "<нет>"
    
    if "analysis_tgt_col" not in st.session_state:
        st.session_state["analysis_tgt_col"] = "<нет>"
    
    if "analysis_id_col" not in st.session_state:
        st.session_state["analysis_id_col"] = "<нет>"
    
    if "analysis_static_feats" not in st.session_state:
        st.session_state["analysis_static_feats"] = []
    
    # Опции загрузки данных
    upload_options = [
        "Загрузить новые данные", 
        "Использовать данные с главной страницы"
    ]
    upload_choice = st.radio("Источник данных:", upload_options)
    
    if upload_choice == "Загрузить новые данные":
        # Настройки для больших файлов
        with st.expander("Настройки для больших файлов"):
            chunk_size = st.number_input(
                "Размер чанка (строк)",
                min_value=1000,
                max_value=1000000,
                value=100000,
                step=10000,
                help="Для больших файлов (>100 МБ) данные будут загружаться частями. Задайте размер каждой части."
            )
        
        # Загрузка файла
        uploaded_file = st.file_uploader(
            "Выберите файл для анализа", 
            type=["csv", "xls", "xlsx"],
            key="analysis_file_uploader"
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner("Загрузка данных..."):
                    df = load_data(uploaded_file, chunk_size=chunk_size)
                    st.session_state["df_analysis"] = df
                    st.success(f"Файл загружен! Строк: {len(df)}, колонок: {len(df.columns)}")
                    
                    # Показываем превью загруженных данных
                    if len(df) > 1000:
                        st.dataframe(df.head(1000))
                        st.info(f"Показаны первые 1000 из {len(df)} строк.")
                    else:
                        st.dataframe(df)
                    
                    # Показываем статистику
                    with st.expander("Статистика данных", expanded=True):
                        show_dataset_stats(df)
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                logging.error(f"Ошибка загрузки файла на странице анализа: {e}")
    else:
        # Используем данные с главной страницы
        if "df" in st.session_state and st.session_state["df"] is not None:
            if st.button("Загрузить данные с главной страницы"):
                st.session_state["df_analysis"] = st.session_state["df"].copy()
                
                # Копируем настройки колонок с главной страницы
                if "dt_col_key" in st.session_state and st.session_state["dt_col_key"] != "<нет>":
                    st.session_state["analysis_dt_col"] = st.session_state["dt_col_key"]
                
                if "tgt_col_key" in st.session_state and st.session_state["tgt_col_key"] != "<нет>":
                    st.session_state["analysis_tgt_col"] = st.session_state["tgt_col_key"]
                
                if "id_col_key" in st.session_state and st.session_state["id_col_key"] != "<нет>":
                    st.session_state["analysis_id_col"] = st.session_state["id_col_key"]
                
                if "static_feats_key" in st.session_state:
                    st.session_state["analysis_static_feats"] = st.session_state["static_feats_key"]
                
                st.success("Данные с главной страницы успешно загружены для анализа!")
                
                # Показываем превью
                if len(st.session_state["df_analysis"]) > 1000:
                    st.dataframe(st.session_state["df_analysis"].head(1000))
                    st.info(f"Показаны первые 1000 из {len(st.session_state['df_analysis'])} строк.")
                else:
                    st.dataframe(st.session_state["df_analysis"])
        else:
            st.warning("На главной странице нет загруженных данных. Сначала загрузите данные на главной странице или выберите 'Загрузить новые данные'.")
    
    # Получаем данные для анализа
    df_analysis = st.session_state.get("df_analysis")
    
    if df_analysis is None:
        st.warning("Пожалуйста, загрузите данные для анализа!")
        return
    
    # Выбор колонок для анализа
    st.header("2. Выбор колонок для анализа")
    
    # Получаем список всех колонок
    all_cols = list(df_analysis.columns)
    
    # Проверяем, есть ли выбранные колонки в текущем датафрейме
    dt_stored = st.session_state["analysis_dt_col"]
    tgt_stored = st.session_state["analysis_tgt_col"]
    id_stored = st.session_state["analysis_id_col"]
    
    if dt_stored not in ["<нет>"] + all_cols:
        st.session_state["analysis_dt_col"] = "<нет>"
    if tgt_stored not in ["<нет>"] + all_cols:
        st.session_state["analysis_tgt_col"] = "<нет>"
    if id_stored not in ["<нет>"] + all_cols:
        st.session_state["analysis_id_col"] = "<нет>"
    
    # Выбор колонок
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Исправление: конвертируем индекс в число, а не список с числом
        if dt_stored in all_cols:
            dt_index = all_cols.index(dt_stored) + 1  # +1 из-за опции "<нет>" в начале списка
        else:
            dt_index = 0  # Индекс опции "<нет>"
            
        dt_col = st.selectbox(
            "Колонка с датой", 
            ["<нет>"] + all_cols, 
            index=dt_index,
            key="analysis_dt_col_select"
        )
        st.session_state["analysis_dt_col"] = dt_col
    
    with col2:
        # Исправление для целевой колонки
        if tgt_stored in all_cols:
            tgt_index = all_cols.index(tgt_stored) + 1
        else:
            tgt_index = 0
            
        tgt_col = st.selectbox(
            "Колонка target", 
            ["<нет>"] + all_cols,
            index=tgt_index,
            key="analysis_tgt_col_select"
        )
        st.session_state["analysis_tgt_col"] = tgt_col
    
    with col3:
        # Исправление для ID колонки
        if id_stored in all_cols:
            id_index = all_cols.index(id_stored) + 1
        else:
            id_index = 0
            
        id_col = st.selectbox(
            "Колонка ID", 
            ["<нет>"] + all_cols,
            index=id_index,
            key="analysis_id_col_select"
        )
        st.session_state["analysis_id_col"] = id_col
    
    # Выбор статических признаков (если есть ID)
    if id_col != "<нет>":
        possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
        
        # Фильтруем сохраненные статические признаки, чтобы они существовали в текущем датафрейме
        stored_static_feats = st.session_state["analysis_static_feats"]
        filtered_feats = [feat for feat in stored_static_feats if feat in possible_static]
        
        if len(filtered_feats) != len(stored_static_feats):
            st.session_state["analysis_static_feats"] = filtered_feats
        
        st.multiselect(
            "Статические признаки (до 3):", 
            possible_static,
            default=filtered_feats,
            max_selections=3,
            key="analysis_static_feats_select"
        )
        st.session_state["analysis_static_feats"] = st.session_state["analysis_static_feats_select"]
    
    # Проверяем, выбраны ли необходимые колонки
    if dt_col == "<нет>" or tgt_col == "<нет>":
        st.warning("Для анализа требуется выбрать колонки даты и целевой переменной!")
        return
    
    # Автоматическое преобразование колонки даты
    if not pd.api.types.is_datetime64_any_dtype(df_analysis[dt_col]):
        with st.spinner("Преобразование колонки даты..."):
            df_analysis[dt_col] = pd.to_datetime(df_analysis[dt_col], errors="coerce")
            st.info(f"Колонка {dt_col} преобразована в формат даты.")
    
    # Создаем вкладки для различных типов анализа
    tabs = st.tabs([
        "Валидация данных", 
        "Анализ целевой переменной", 
        "Корреляции и статические признаки",
        "Временной ряд и сезонность",
        "Выявление концепт-дрифта",
        "Разделение данных"
    ])
    
    # 1. Вкладка валидации данных
    with tabs[0]:
        st.header("Валидация данных")
        
        # Кнопка для запуска валидации
        if st.button("Запустить валидацию данных", key="run_validation_btn"):
            with st.spinner("Выполняется валидация данных..."):
                try:
                    validation_results = validate_dataset(df_analysis, dt_col, tgt_col, id_col)
                    display_validation_results(validation_results)
                    
                    # Подсчет строк по ID, если указан
                    if id_col != "<нет>" and id_col in df_analysis.columns:
                        st.subheader("Распределение по ID")
                        id_counts = df_analysis[id_col].value_counts().reset_index()
                        id_counts.columns = [id_col, "Количество"]
                        
                        # Отображаем таблицу и график
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.dataframe(id_counts)
                        
                        with col2:
                            fig = px.bar(id_counts, x=id_col, y="Количество", 
                                        title=f"Количество строк по {id_col}")
                            st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Ошибка при валидации данных: {e}")
                    logging.error(f"Ошибка при валидации данных: {e}")
    
    # 2. Вкладка анализа целевой переменной
    with tabs[1]:
        st.header("Анализ целевой переменной")
        
        # Создаем подвкладки
        target_tabs = st.tabs(["Распределение", "Временной ряд", "Аномалии/выбросы", "Трансформации"])
        
        # 2.1 Распределение целевой переменной
        with target_tabs[0]:
            st.subheader("Распределение целевой переменной")
            
            # График распределения
            fig_dist = plot_target_distribution(df_analysis, tgt_col)
            if fig_dist:
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                st.warning(f"Не удалось построить график распределения для колонки {tgt_col}")
            
            # Боксплот
            fig_box = plot_target_boxplot(df_analysis, tgt_col, id_col)
            if fig_box:
                st.plotly_chart(fig_box, use_container_width=True)
            else:
                st.warning(f"Не удалось построить боксплот для колонки {tgt_col}")
            
            # Основные статистики
            if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                st.subheader("Статистики целевой переменной")
                stats = df_analysis[tgt_col].describe()
                st.dataframe(stats)
        
        # 2.2 Временной ряд
        with target_tabs[1]:
            st.subheader("Временной ряд целевой переменной")
            
            # График временного ряда
            fig_ts = plot_target_time_series(df_analysis, dt_col, tgt_col, id_col)
            if fig_ts:
                st.plotly_chart(fig_ts, use_container_width=True)
            else:
                st.warning(f"Не удалось построить временной ряд для колонок {dt_col} и {tgt_col}")
            
            # Сезонные паттерны
            st.subheader("Сезонные паттерны")
            if st.button("Проанализировать сезонные паттерны", key="analyze_seasonal_btn"):
                with st.spinner("Анализ сезонных паттернов..."):
                    try:
                        seasonal_results = analyze_seasonal_patterns(df_analysis, dt_col, tgt_col, id_col)
                        
                        if "error" in seasonal_results:
                            st.error(f"Ошибка при анализе сезонности: {seasonal_results['error']}")
                        else:
                            # Отображение по месяцам
                            if 'figures' in seasonal_results and 'monthly' in seasonal_results['figures']:
                                st.write("#### Сезонность по месяцам")
                                st.plotly_chart(seasonal_results['figures']['monthly'], use_container_width=True)
                            
                            # Отображение по дням недели
                            if 'figures' in seasonal_results and 'weekday' in seasonal_results['figures']:
                                st.write("#### Сезонность по дням недели")
                                st.plotly_chart(seasonal_results['figures']['weekday'], use_container_width=True)
                            
                            # Отображение по кварталам
                            if 'figures' in seasonal_results and 'quarterly' in seasonal_results['figures']:
                                st.write("#### Сезонность по кварталам")
                                st.plotly_chart(seasonal_results['figures']['quarterly'], use_container_width=True)
                    except Exception as e:
                        st.error(f"Ошибка при анализе сезонности: {e}")
                        logging.error(f"Ошибка при анализе сезонности: {e}")
            
            # Автокорреляция
            st.subheader("Автокорреляция")
            if st.button("Проанализировать автокорреляцию", key="analyze_autocorr_btn"):
                with st.spinner("Анализ автокорреляции..."):
                    try:
                        max_lag = st.slider("Максимальный лаг", 5, 100, 30)
                        autocorr_results = detect_autocorrelation(df_analysis, dt_col, tgt_col, id_col, max_lag=max_lag)
                        
                        if 'error' in autocorr_results:
                            st.error(f"Ошибка при анализе автокорреляции: {autocorr_results['error']}")
                        else:
                            # Отображение ACF
                            if 'figures' in autocorr_results and 'acf' in autocorr_results['figures']:
                                st.write("#### Автокорреляционная функция (ACF)")
                                st.plotly_chart(autocorr_results['figures']['acf'], use_container_width=True)
                            
                            # Отображение PACF
                            if 'figures' in autocorr_results and 'pacf' in autocorr_results['figures']:
                                st.write("#### Частичная автокорреляционная функция (PACF)")
                                st.plotly_chart(autocorr_results['figures']['pacf'], use_container_width=True)
                            
                            # Интерпретация
                            if 'analyzed_id' in autocorr_results:
                                st.info(f"Анализ проведен для ID={autocorr_results['analyzed_id']} (самый длинный временной ряд).")
                    except Exception as e:
                        st.error(f"Ошибка при анализе автокорреляции: {e}")
                        logging.error(f"Ошибка при анализе автокорреляции: {e}")
        
        # 2.3 Аномалии/выбросы
        with target_tabs[2]:
            st.subheader("Обнаружение выбросов в целевой переменной")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                outlier_method = st.selectbox(
                    "Метод обнаружения выбросов",
                    ["IQR (межквартильный размах)", "Z-score (стандартное отклонение)"],
                    key="outlier_method"
                )
                
                method_map = {
                    "IQR (межквартильный размах)": "iqr",
                    "Z-score (стандартное отклонение)": "zscore"
                }
                
                if st.button("Найти выбросы", key="find_outliers_btn"):
                    if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                        with st.spinner("Поиск выбросов..."):
                            try:
                                clean_df, outliers_df = detect_outliers(
                                    df_analysis, tgt_col, id_col if id_col != "<нет>" else None, 
                                    method=method_map[outlier_method]
                                )
                                
                                st.session_state["clean_df"] = clean_df
                                st.session_state["outliers_df"] = outliers_df
                                
                                st.success(f"Найдено {len(outliers_df)} выбросов ({len(outliers_df)/len(df_analysis)*100:.2f}% от всех данных).")
                            except Exception as e:
                                st.error(f"Ошибка при поиске выбросов: {e}")
                                logging.error(f"Ошибка при поиске выбросов: {e}")
                    else:
                        st.error(f"Не удалось найти колонку {tgt_col} для поиска выбросов")
            
            with col2:
                # Если были обнаружены выбросы, показываем их на графике
                if "outliers_df" in st.session_state and "clean_df" in st.session_state:
                    outliers_df = st.session_state["outliers_df"]
                    clean_df = st.session_state["clean_df"]
                    
                    if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns and not outliers_df.empty:
                        # Создаем датафрейм для графика
                        plot_df = pd.DataFrame()
                        clean_df_plot = clean_df.copy()
                        clean_df_plot['type'] = 'Normal'
                        
                        outliers_df_plot = outliers_df.copy()
                        outliers_df_plot['type'] = 'Outlier'
                        
                        plot_df = pd.concat([clean_df_plot, outliers_df_plot])
                        
                        # Строим график
                        fig = px.scatter(
                            plot_df, x=dt_col, y=tgt_col, color='type',
                            title="Обнаружение выбросов",
                            color_discrete_map={'Normal': 'blue', 'Outlier': 'red'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Показываем распределение выбросов
                        if id_col != "<нет>" and id_col in outliers_df.columns:
                            outlier_counts = outliers_df[id_col].value_counts().reset_index()
                            outlier_counts.columns = [id_col, "Количество выбросов"]
                            
                            st.write("#### Распределение выбросов по ID")
                            st.dataframe(outlier_counts)
            
            # Кнопки для экспорта
            if "clean_df" in st.session_state and "outliers_df" in st.session_state:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Использовать данные без выбросов", key="use_clean_data_btn"):
                        st.session_state["df_analysis"] = st.session_state["clean_df"]
                        st.success("Теперь используются данные без выбросов для текущего анализа!")
                
                with col2:
                    if st.button("Восстановить исходные данные", key="restore_original_data_btn"):
                        st.session_state["df_analysis"] = df_analysis
                        st.success("Восстановлены исходные данные.")
                
                # Добавляем новый блок для экспорта и информации по использованию
                st.subheader("Экспорт и использование очищенных данных")
                
                # Колонки для выгрузки разных типов данных
                exp_col1, exp_col2 = st.columns(2)
                
                with exp_col1:
                    st.write("#### Данные без выбросов")
                    download_excel(st.session_state["clean_df"], "clean_data.xlsx")
                
                with exp_col2:
                    st.write("#### Данные с выбросами")
                    download_excel(st.session_state["outliers_df"], "outliers_data.xlsx")
                
                # Кнопка для передачи очищенных данных на главную страницу
                if st.button("Использовать данные без выбросов на главной странице", key="use_clean_data_main_btn"):
                    st.session_state["df"] = st.session_state["clean_df"]
                    st.success("Данные без выбросов переданы на главную страницу!")
                
                # Информация о том, как использовать очищенные данные
                show_data_usage_info("очищенные данные")
        
        # 2.4 Трансформации
        with target_tabs[3]:
            st.subheader("Трансформации целевой переменной")
            
            # Выбор трансформации
            transformation = st.selectbox(
                "Выберите тип трансформации",
                ["Нет", "Логарифмическая (log)", "Корень квадратный (sqrt)", "Box-Cox", "Yeo-Johnson"],
                key="transformation_type"
            )
            
            # Строим график и применяем трансформацию при нажатии кнопки
            if st.button("Применить трансформацию", key="apply_transform_btn"):
                if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                    with st.spinner("Применение трансформации..."):
                        # Словарь соответствия трансформаций
                        transform_map = {
                            "Нет": None,
                            "Логарифмическая (log)": "log",
                            "Корень квадратный (sqrt)": "sqrt",
                            "Box-Cox": "box-cox",
                            "Yeo-Johnson": "yeo-johnson"
                        }
                        
                        if transformation != "Нет":
                            try:
                                # Применяем трансформацию
                                transformed_df = apply_target_transformations(
                                    df_analysis, tgt_col, transformation=transform_map[transformation]
                                )
                                
                                # Сохраняем в session_state
                                st.session_state["transformed_df"] = transformed_df
                                st.session_state["applied_transformation"] = transform_map[transformation]
                                
                                # Отображаем графики "до" и "после"
                                fig = make_subplots(
                                    rows=1, cols=2,
                                    subplot_titles=("До трансформации", "После трансформации")
                                )
                                
                                # Гистограмма до трансформации
                                fig.add_trace(
                                    go.Histogram(x=df_analysis[tgt_col], name="До"),
                                    row=1, col=1
                                )
                                
                                # Гистограмма после трансформации
                                fig.add_trace(
                                    go.Histogram(x=transformed_df[tgt_col], name="После"),
                                    row=1, col=2
                                )
                                
                                fig.update_layout(
                                    title_text=f"Эффект {transformation} трансформации",
                                    showlegend=False
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Сравнение статистик
                                st.subheader("Сравнение статистик")
                                
                                stats_before = df_analysis[tgt_col].describe()
                                stats_after = transformed_df[tgt_col].describe()
                                
                                stats_comparison = pd.DataFrame({
                                    "До трансформации": stats_before,
                                    "После трансформации": stats_after
                                })
                                
                                st.dataframe(stats_comparison)
                                
                                # Кнопка для использования трансформированных данных
                                if st.button("Использовать трансформированные данные", key="use_transformed_data_btn"):
                                    st.session_state["df_analysis"] = transformed_df
                                    st.success(f"Теперь используются данные с {transformation} трансформацией!")
                            except Exception as e:
                                st.error(f"Ошибка при применении трансформации: {e}")
                                logging.error(f"Ошибка при применении трансформации: {e}")
                        else:
                            st.info("Трансформация не выбрана.")
                else:
                    st.error(f"Не удалось найти колонку {tgt_col} для трансформации")
            
            # После трансформации добавляем экспорт
            if "transformed_df" in st.session_state:
                st.subheader("Экспорт и использование трансформированных данных")
                
                # Кнопка выгрузки в Excel
                download_excel(st.session_state["transformed_df"], "transformed_data.xlsx")
                
                # Кнопка для передачи трансформированных данных на главную страницу
                if st.button("Использовать трансформированные данные на главной странице", key="use_transformed_main_btn"):
                    st.session_state["df"] = st.session_state["transformed_df"]
                    st.success("Трансформированные данные переданы на главную страницу!")
                
                # Информация о том, как использовать трансформированные данные
                show_data_usage_info("трансформированные данные")
    
    # 3. Вкладка корреляций и статических признаков
    with tabs[2]:
        st.header("Анализ корреляций и статических признаков")
        
        # Получаем статические признаки
        static_feats = st.session_state.get("analysis_static_feats", [])
        
        if not static_feats:
            st.warning("Статические признаки не выбраны. Выберите их в разделе 'Выбор колонок для анализа'.")
        else:
            if st.button("Анализировать корреляции", key="analyze_correlations_btn"):
                with st.spinner("Анализ корреляций..."):
                    try:
                        correlation_results = analyze_correlations(df_analysis, static_feats, tgt_col)
                        display_correlation_results(correlation_results)
                        
                        # Сохраняем результаты в session_state
                        st.session_state["correlation_results"] = correlation_results
                    except Exception as e:
                        st.error(f"Ошибка при анализе корреляций: {e}")
                        logging.error(f"Ошибка при анализе корреляций: {e}")
    
    # 4. Вкладка временного ряда и сезонности
    with tabs[3]:
        st.header("Анализ временного ряда и сезонности")
        
        # Создаем подвкладки
        ts_tabs = st.tabs(["Декомпозиция", "Генерация признаков"])
        
        # 4.1 Декомпозиция временного ряда
        with ts_tabs[0]:
            st.subheader("Декомпозиция временного ряда")
            
            period = st.number_input(
                "Период сезонности (оставьте 0 для автоопределения)",
                min_value=0,
                max_value=365,
                value=0,
                key="decomposition_period"
            )
            
            if st.button("Выполнить декомпозицию", key="decompose_btn"):
                if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns and tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                    with st.spinner("Выполняется декомпозиция временного ряда..."):
                        try:
                            decomposition_results = decompose_time_series(
                                df_analysis, dt_col, tgt_col, 
                                id_col if id_col != "<нет>" else None,
                                period=None if period == 0 else period
                            )
                            display_decomposition_results(decomposition_results)
                            
                            # Сохраняем результаты в session_state
                            st.session_state["decomposition_results"] = decomposition_results
                        except Exception as e:
                            st.error(f"Ошибка при декомпозиции временного ряда: {e}")
                            logging.error(f"Ошибка при декомпозиции временного ряда: {e}")
                else:
                    st.error(f"Не удалось найти колонки {dt_col} и {tgt_col} для декомпозиции")
        
        # 4.2 Генерация признаков
        with ts_tabs[1]:
            st.subheader("Генерация временных признаков")
            
            # Создаем подвкладки для различных типов признаков
            feat_tabs = st.tabs(["Временные компоненты", "Лаговые признаки", "Скользящие признаки"])
            
            # 4.2.1 Временные компоненты
            with feat_tabs[0]:
                st.write("#### Временные компоненты (год, месяц, день недели и т.д.)")
                
                time_features = st.multiselect(
                    "Выберите временные компоненты для генерации",
                    [
                        'year', 'month', 'day', 'dayofweek', 'quarter', 'hour', 'minute',
                        'is_weekend', 'is_month_start', 'is_month_end',
                        'sin_month', 'cos_month', 'sin_day', 'cos_day',
                        'sin_dayofweek', 'cos_dayofweek'
                    ],
                    default=['year', 'month', 'dayofweek', 'is_weekend', 'sin_month', 'cos_month'],
                    key="time_features"
                )
                
                if st.button("Сгенерировать временные признаки", key="generate_time_features_btn"):
                    if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns:
                        with st.spinner("Генерация временных признаков..."):
                            if time_features:
                                try:
                                    # Генерируем признаки
                                    df_with_time_features = add_time_features(df_analysis, dt_col, features=time_features)
                                    
                                    # Показываем примеры новых признаков
                                    st.subheader("Примеры сгенерированных признаков")
                                    display_cols = [dt_col] + [f for f in time_features if f in df_with_time_features.columns]
                                    st.dataframe(df_with_time_features[display_cols].head(10))
                                    
                                    # Сохраняем в session_state
                                    st.session_state["df_with_time_features"] = df_with_time_features
                                    
                                    # Кнопка для использования новых данных
                                    if st.button("Использовать данные с временными признаками", key="use_time_features_btn"):
                                        st.session_state["df_analysis"] = df_with_time_features
                                        st.success("Теперь используются данные с временными признаками!")
                                except Exception as e:
                                    st.error(f"Ошибка при генерации временных признаков: {e}")
                                    logging.error(f"Ошибка при генерации временных признаков: {e}")
                            else:
                                st.warning("Выберите хотя бы один временной признак.")
                    else:
                        st.error(f"Не удалось найти колонку даты {dt_col} для генерации признаков")
                
                # После генерации временных признаков добавляем экспорт
                if "df_with_time_features" in st.session_state:
                    st.subheader("Экспорт и использование данных с временными признаками")
                    
                    # Кнопка выгрузки в Excel
                    download_excel(st.session_state["df_with_time_features"], "time_features_data.xlsx")
                    
                    # Кнопка для передачи данных с временными признаками на главную страницу
                    if st.button("Использовать данные с временными признаками на главной странице", key="use_time_features_main_btn"):
                        st.session_state["df"] = st.session_state["df_with_time_features"]
                        st.success("Данные с временными признаками переданы на главную страницу!")
                    
                    # Информация о том, как использовать временные признаки
                    show_data_usage_info("временные признаки")
                    
                    # Дополнительная информация о временных признаках
                    st.info("""
                    **Как использовать временные признаки:**
                    
                    Эти признаки помогают модели учитывать сезонность и цикличность. Особенно полезны:
                    
                    - `sin_month` и `cos_month` - циклическое представление месяцев
                    - `is_weekend` - бинарный признак выходных дней
                    - `quarter` - квартал года
                    
                    При построении модели эти признаки позволяют учесть календарные закономерности в данных.
                    """)
            
            # 4.2.2 Лаговые признаки
            with feat_tabs[1]:
                st.write("#### Лаговые признаки (значения с предыдущих периодов)")
                
                # Ввод лагов через текстовое поле
                lag_input = st.text_input(
                    "Введите периоды лагов через запятую (например: 1,7,14,28)",
                    value="1,7,14,28",
                    key="lag_input"
                )
                
                # Преобразуем ввод в список чисел
                try:
                    lag_periods = [int(x.strip()) for x in lag_input.split(",") if x.strip()]
                except ValueError:
                    st.error("Ошибка ввода! Используйте только числа, разделенные запятыми.")
                    lag_periods = []
                
                if st.button("Сгенерировать лаговые признаки", key="generate_lag_features_btn"):
                    if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns and tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                        with st.spinner("Генерация лаговых признаков..."):
                            if lag_periods:
                                try:
                                    # Генерируем признаки
                                    df_with_lags = generate_lag_features(
                                        df_analysis, tgt_col, dt_col, 
                                        id_col if id_col != "<нет>" and id_col in df_analysis.columns else None, 
                                        lag_periods=lag_periods
                                    )
                                    
                                    # Показываем примеры новых признаков
                                    lag_columns = [f"{tgt_col}_lag_{lag}" for lag in lag_periods if f"{tgt_col}_lag_{lag}" in df_with_lags.columns]
                                    
                                    st.subheader("Примеры сгенерированных лаговых признаков")
                                    display_cols = [dt_col, tgt_col] + lag_columns
                                    if id_col != "<нет>" and id_col in df_with_lags.columns:
                                        display_cols.insert(0, id_col)
                                    
                                    st.dataframe(df_with_lags[display_cols].head(10))
                                    
                                    # Сохраняем в session_state
                                    st.session_state["df_with_lags"] = df_with_lags
                                    
                                    # Количество NaN в новых признаках
                                    na_counts = df_with_lags[lag_columns].isna().sum()
                                    
                                    st.subheader("Количество пропусков (NaN) в лаговых признаках")
                                    st.dataframe(na_counts)
                                    
                                    # Кнопка для использования новых данных
                                    if st.button("Использовать данные с лаговыми признаками", key="use_lag_features_btn"):
                                        st.session_state["df_analysis"] = df_with_lags
                                        st.success("Теперь используются данные с лаговыми признаками!")
                                except Exception as e:
                                    st.error(f"Ошибка при генерации лаговых признаков: {e}")
                                    logging.error(f"Ошибка при генерации лаговых признаков: {e}")
                            else:
                                st.warning("Введите хотя бы один период лага.")
                    else:
                        st.error(f"Не удалось найти колонки {dt_col} и {tgt_col} для генерации лаговых признаков")
                
                # После генерации лаговых признаков добавляем экспорт
                if "df_with_lags" in st.session_state:
                    st.subheader("Экспорт и использование данных с лаговыми признаками")
                    
                    # Кнопка выгрузки в Excel
                    download_excel(st.session_state["df_with_lags"], "lag_features_data.xlsx")
                    
                    # Кнопка для передачи данных с лагами на главную страницу
                    if st.button("Использовать данные с лаговыми признаками на главной странице", key="use_lag_features_main_btn"):
                        st.session_state["df"] = st.session_state["df_with_lags"]
                        st.success("Данные с лаговыми признаками переданы на главную страницу!")
                    
                    # Информация о том, как использовать лаговые признаки
                    show_data_usage_info("лаговые признаки")
                    
                    # Дополнительная информация о лаговых признаках
                    st.info("""
                    **Как использовать лаговые признаки:**
                    
                    Лаговые признаки особенно важны для прогнозирования временных рядов, так как позволяют модели учитывать:
                    
                    - Недавнюю историю (лаги 1-7)
                    - Среднесрочную историю (лаги 7-30)
                    - Долгосрочные зависимости (лаги > 30)
                    
                    При прогнозировании убедитесь, что в модель передаются только те лаги, которые будут доступны на момент прогноза.
                    Обратите внимание на пропуски (NaN) в начале временных рядов.
                    """)
            
            # 4.2.3 Скользящие признаки
            with feat_tabs[2]:
                st.write("#### Скользящие признаки (статистики из окна наблюдений)")
                
                # Ввод размеров окон
                window_input = st.text_input(
                    "Введите размеры окон через запятую (например: 7,14,30)",
                    value="7,14,30",
                    key="window_input"
                )
                
                # Выбор функций
                window_functions = st.multiselect(
                    "Выберите функции для скользящих окон",
                    ["mean", "std", "min", "max"],
                    default=["mean", "std"],
                    key="window_functions"
                )
                
                # Преобразуем ввод в список чисел
                try:
                    windows = [int(x.strip()) for x in window_input.split(",") if x.strip()]
                except ValueError:
                    st.error("Ошибка ввода! Используйте только числа, разделенные запятыми.")
                    windows = []
                
                if st.button("Сгенерировать скользящие признаки", key="generate_rolling_features_btn"):
                    if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns and tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                        with st.spinner("Генерация скользящих признаков..."):
                            if windows and window_functions:
                                try:
                                    # Генерируем признаки
                                    df_with_rolling = generate_rolling_features(
                                        df_analysis, tgt_col, dt_col, 
                                        id_col if id_col != "<нет>" and id_col in df_analysis.columns else None,
                                        windows=windows, functions=window_functions
                                    )
                                    
                                    # Показываем примеры новых признаков
                                    rolling_columns = [
                                        f"{tgt_col}_rolling_{window}_{func}"
                                        for window in windows
                                        for func in window_functions
                                        if f"{tgt_col}_rolling_{window}_{func}" in df_with_rolling.columns
                                    ]
                                    
                                    st.subheader("Примеры сгенерированных скользящих признаков")
                                    display_cols = [dt_col, tgt_col] 
                                    if rolling_columns:
                                        display_cols.extend(rolling_columns[:3])  # Ограничиваем для читаемости
                                    if id_col != "<нет>" and id_col in df_with_rolling.columns:
                                        display_cols.insert(0, id_col)
                                    
                                    st.dataframe(df_with_rolling[display_cols].head(10))
                                    
                                    # Показываем все созданные признаки
                                    st.subheader("Все созданные скользящие признаки")
                                    st.write(rolling_columns)
                                    
                                    # Сохраняем в session_state
                                    st.session_state["df_with_rolling"] = df_with_rolling
                                    
                                    # Кнопка для использования новых данных
                                    if st.button("Использовать данные со скользящими признаками", key="use_rolling_features_btn"):
                                        st.session_state["df_analysis"] = df_with_rolling
                                        st.success("Теперь используются данные со скользящими признаками!")
                                except Exception as e:
                                    st.error(f"Ошибка при генерации скользящих признаков: {e}")
                                    logging.error(f"Ошибка при генерации скользящих признаков: {e}")
                            else:
                                st.warning("Выберите хотя бы один размер окна и одну функцию.")
                    else:
                        st.error(f"Не удалось найти колонки {dt_col} и {tgt_col} для генерации скользящих признаков")
                
                # После генерации скользящих признаков добавляем экспорт
                if "df_with_rolling" in st.session_state:
                    st.subheader("Экспорт и использование данных со скользящими признаками")
                    
                    # Кнопка выгрузки в Excel
                    download_excel(st.session_state["df_with_rolling"], "rolling_features_data.xlsx")
                    
                    # Кнопка для передачи данных со скользящими признаками на главную страницу
                    if st.button("Использовать данные со скользящими признаками на главной странице", key="use_rolling_features_main_btn"):
                        st.session_state["df"] = st.session_state["df_with_rolling"]
                        st.success("Данные со скользящими признаками переданы на главную страницу!")
                    
                    # Информация о том, как использовать скользящие признаки
                    show_data_usage_info("скользящие признаки")
                    
                    # Дополнительная информация о скользящих признаках
                    st.info("""
                    **Как использовать скользящие признаки:**
                    
                    Скользящие признаки (rolling features) помогают выявить тренды и снизить шум в данных:
                    
                    - Скользящее среднее (`mean`) - сглаживает ряд, выявляет тренды
                    - Скользящее стандартное отклонение (`std`) - оценивает волатильность
                    - Скользящие минимум/максимум (`min`/`max`) - выявляют экстремумы за период
                    
                    Эти признаки могут существенно повысить качество прогноза, особенно в сочетании с лаговыми признаками.
                    Для прогнозирования обратите внимание на то, что скользящие признаки тоже содержат пропуски в начале рядов.
                    """)
    
    # 5. Вкладка выявления концепт-дрифта
    with tabs[4]:
        st.header("Выявление концепт-дрифта")
        
        st.write("""
        Концепт-дрифт - это явление изменения статистических свойств целевой переменной с течением времени.
        Для его обнаружения необходимо разделить данные на две части: исторические (train) и новые (test).
        """)
        
        # Варианты разделения
        split_method = st.radio(
            "Способ разделения данных",
            ["По дате", "По доле данных"],
            key="drift_split_method"
        )
        
        if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns and tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
            if split_method == "По дате":
                # Получаем минимальную и максимальную даты
                if not pd.api.types.is_datetime64_any_dtype(df_analysis[dt_col]):
                    df_dates = df_analysis.copy()
                    df_dates[dt_col] = pd.to_datetime(df_dates[dt_col], errors="coerce")
                else:
                    df_dates = df_analysis
                
                min_date = df_dates[dt_col].min().date()
                max_date = df_dates[dt_col].max().date()
                
                # Выбор даты разделения
                split_date = st.date_input(
                    "Выберите дату разделения",
                    value=pd.Timestamp(max_date) - pd.Timedelta(days=30),
                    min_value=pd.Timestamp(min_date),
                    max_value=pd.Timestamp(max_date),
                    key="drift_split_date"
                )
                
                if st.button("Проверить концепт-дрифт", key="check_drift_btn"):
                    with st.spinner("Проверка концепт-дрифта..."):
                        try:
                            # Преобразуем выбранную дату в timestamp
                            split_timestamp = pd.Timestamp(split_date)
                            
                            # Разделяем данные
                            historical_df = df_dates[df_dates[dt_col] < split_timestamp]
                            new_df = df_dates[df_dates[dt_col] >= split_timestamp]
                            
                            if len(historical_df) < 10 or len(new_df) < 10:
                                st.error("Недостаточно данных для анализа. Убедитесь, что в обоих наборах есть хотя бы 10 записей.")
                            else:
                                st.success(f"Данные разделены: {len(historical_df)} исторических и {len(new_df)} новых записей.")
                                
                                # Обнаружение дрифта
                                drift_results = detect_concept_drift(
                                    historical_df, new_df, tgt_col, dt_col, 
                                    id_col if id_col != "<нет>" and id_col in df_analysis.columns else None
                                )
                                display_drift_results(drift_results)
                        except Exception as e:
                            st.error(f"Ошибка при проверке концепт-дрифта: {e}")
                            logging.error(f"Ошибка при проверке концепт-дрифта: {e}")
            else:  # По доле данных
                # Выбор доли данных для теста
                test_size = st.slider(
                    "Доля новых данных",
                    min_value=0.1,
                    max_value=0.5,
                    value=0.2,
                    step=0.05,
                    key="drift_test_size"
                )
                
                if st.button("Проверить концепт-дрифт", key="check_drift_ratio_btn"):
                    with st.spinner("Проверка концепт-дрифта..."):
                        try:
                            # Убеждаемся, что колонка даты в формате datetime
                            if not pd.api.types.is_datetime64_any_dtype(df_analysis[dt_col]):
                                df_dates = df_analysis.copy()
                                df_dates[dt_col] = pd.to_datetime(df_dates[dt_col], errors="coerce")
                            else:
                                df_dates = df_analysis
                            
                            # Сортируем данные по дате
                            df_sorted = df_dates.sort_values(dt_col)
                            
                            # Разделяем данные
                            split_idx = int(len(df_sorted) * (1 - test_size))
                            historical_df = df_sorted.iloc[:split_idx]
                            new_df = df_sorted.iloc[split_idx:]
                            
                            if len(historical_df) < 10 or len(new_df) < 10:
                                st.error("Недостаточно данных для анализа. Убедитесь, что в обоих наборах есть хотя бы 10 записей.")
                            else:
                                st.success(f"Данные разделены: {len(historical_df)} исторических и {len(new_df)} новых записей.")
                                
                                # Обнаружение дрифта
                                drift_results = detect_concept_drift(
                                    historical_df, new_df, tgt_col, dt_col, 
                                    id_col if id_col != "<нет>" and id_col in df_analysis.columns else None
                                )
                                display_drift_results(drift_results)
                        except Exception as e:
                            st.error(f"Ошибка при проверке концепт-дрифта: {e}")
                            logging.error(f"Ошибка при проверке концепт-дрифта: {e}")
        else:
            st.error(f"Не удалось найти колонки {dt_col} и {tgt_col} для проверки концепт-дрифта")
    
    # 6. Вкладка разделения данных
    with tabs[5]:
        st.header("Разделение данных на обучающую и тестовую выборки")
        
        # Варианты разделения
        split_method = st.radio(
            "Способ разделения данных",
            ["По дате", "По доле данных"],
            key="split_method"
        )
        
        if dt_col and dt_col != "<нет>" and dt_col in df_analysis.columns:
            if split_method == "По дате":
                # Получаем минимальную и максимальную даты
                if not pd.api.types.is_datetime64_any_dtype(df_analysis[dt_col]):
                    df_dates = df_analysis.copy()
                    df_dates[dt_col] = pd.to_datetime(df_dates[dt_col], errors="coerce")
                else:
                    df_dates = df_analysis
                
                min_date = df_dates[dt_col].min().date()
                max_date = df_dates[dt_col].max().date()
                
                # Выбор даты разделения
                split_date = st.date_input(
                    "Выберите дату разделения",
                    value=pd.Timestamp(max_date) - pd.Timedelta(days=30),
                    min_value=pd.Timestamp(min_date),
                    max_value=pd.Timestamp(max_date),
                    key="split_date"
                )
                
                # Опция для валидационной выборки
                use_validation = st.checkbox("Использовать валидационную выборку", key="use_validation")
                
                if use_validation:
                    val_date = st.date_input(
                        "Выберите дату разделения для валидационной выборки",
                        value=pd.Timestamp(split_date) - pd.Timedelta(days=30),
                        min_value=pd.Timestamp(min_date),
                        max_value=pd.Timestamp(split_date),
                        key="val_date"
                    )
                
                if st.button("Разделить данные", key="split_data_btn"):
                    with st.spinner("Разделение данных..."):
                        try:
                            # Преобразуем выбранную дату в timestamp
                            split_timestamp = pd.Timestamp(split_date)
                            
                            if use_validation:
                                val_timestamp = pd.Timestamp(val_date)
                                
                                # Разделяем данные
                                train_df = df_dates[df_dates[dt_col] < val_timestamp]
                                val_df = df_dates[(df_dates[dt_col] >= val_timestamp) & (df_dates[dt_col] < split_timestamp)]
                                test_df = df_dates[df_dates[dt_col] >= split_timestamp]
                                
                                if len(train_df) < 10 or len(val_df) < 10 or len(test_df) < 10:
                                    st.error("Недостаточно данных для разделения. Убедитесь, что в каждой выборке есть хотя бы 10 записей.")
                                else:
                                    st.success(f"Данные разделены: {len(train_df)} обучающих, {len(val_df)} валидационных и {len(test_df)} тестовых записей.")
                                    
                                    # Сохраняем в session_state
                                    st.session_state["train_df"] = train_df
                                    st.session_state["val_df"] = val_df
                                    st.session_state["test_df"] = test_df
                                    
                                    # Отображаем распределение целевой переменной
                                    if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                                        train_df['dataset'] = 'Train'
                                        val_df['dataset'] = 'Validation'
                                        test_df['dataset'] = 'Test'
                                        
                                        combined_df = pd.concat([train_df, val_df, test_df])
                                        
                                        fig = px.box(
                                            combined_df, x='dataset', y=tgt_col,
                                            title="Распределение целевой переменной по выборкам"
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                            else:
                                # Разделяем данные
                                train_df = df_dates[df_dates[dt_col] < split_timestamp]
                                test_df = df_dates[df_dates[dt_col] >= split_timestamp]
                                
                                if len(train_df) < 10 or len(test_df) < 10:
                                    st.error("Недостаточно данных для разделения. Убедитесь, что в каждой выборке есть хотя бы 10 записей.")
                                else:
                                    st.success(f"Данные разделены: {len(train_df)} обучающих и {len(test_df)} тестовых записей.")
                                    
                                    # Сохраняем в session_state
                                    st.session_state["train_df"] = train_df
                                    st.session_state["test_df"] = test_df
                                    st.session_state["val_df"] = None
                                    
                                    # Отображаем распределение целевой переменной
                                    if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                                        train_df['dataset'] = 'Train'
                                        test_df['dataset'] = 'Test'
                                        
                                        combined_df = pd.concat([train_df, test_df])
                                        
                                        fig = px.box(
                                            combined_df, x='dataset', y=tgt_col,
                                            title="Распределение целевой переменной по выборкам"
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Ошибка при разделении данных: {e}")
                            logging.error(f"Ошибка при разделении данных: {e}")
            else:  # По доле данных
                # Выбор доли данных для теста
                test_size = st.slider(
                    "Доля тестовых данных",
                    min_value=0.1,
                    max_value=0.5,
                    value=0.2,
                    step=0.05,
                    key="test_size"
                )
                
                # Опция для валидационной выборки
                use_validation = st.checkbox("Использовать валидационную выборку", key="use_validation_ratio")
                
                if use_validation:
                    val_size = st.slider(
                        "Доля валидационных данных",
                        min_value=0.05,
                        max_value=0.3,
                        value=0.1,
                        step=0.05,
                        key="val_size"
                    )
                    
                    # Проверка, что сумма долей не превышает 0.8
                    if test_size + val_size > 0.8:
                        st.warning("Суммарная доля тестовых и валидационных данных слишком большая. Рекомендуется уменьшить.")
                
                if st.button("Разделить данные", key="split_data_ratio_btn"):
                    with st.spinner("Разделение данных..."):
                        try:
                            if use_validation:
                                train_df, test_df, val_df = split_train_test(
                                    df_analysis, dt_col, test_size=test_size, validation_size=val_size
                                )
                                
                                if len(train_df) < 10 or len(val_df) < 10 or len(test_df) < 10:
                                    st.error("Недостаточно данных для разделения. Убедитесь, что в каждой выборке есть хотя бы 10 записей.")
                                else:
                                    st.success(f"Данные разделены: {len(train_df)} обучающих, {len(val_df)} валидационных и {len(test_df)} тестовых записей.")
                                    
                                    # Сохраняем в session_state
                                    st.session_state["train_df"] = train_df
                                    st.session_state["val_df"] = val_df
                                    st.session_state["test_df"] = test_df
                                    
                                    # Отображаем распределение целевой переменной
                                    if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                                        train_df['dataset'] = 'Train'
                                        val_df['dataset'] = 'Validation'
                                        test_df['dataset'] = 'Test'
                                        
                                        combined_df = pd.concat([train_df, val_df, test_df])
                                        
                                        fig = px.box(
                                            combined_df, x='dataset', y=tgt_col,
                                            title="Распределение целевой переменной по выборкам"
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                            else:
                                train_df, test_df, _ = split_train_test(
                                    df_analysis, dt_col, test_size=test_size, validation_size=0.0
                                )
                                
                                if len(train_df) < 10 or len(test_df) < 10:
                                    st.error("Недостаточно данных для разделения. Убедитесь, что в каждой выборке есть хотя бы 10 записей.")
                                else:
                                    st.success(f"Данные разделены: {len(train_df)} обучающих и {len(test_df)} тестовых записей.")
                                    
                                    # Сохраняем в session_state
                                    st.session_state["train_df"] = train_df
                                    st.session_state["test_df"] = test_df
                                    st.session_state["val_df"] = None
                                    
                                    # Отображаем распределение целевой переменной
                                    if tgt_col and tgt_col != "<нет>" and tgt_col in df_analysis.columns:
                                        train_df['dataset'] = 'Train'
                                        test_df['dataset'] = 'Test'
                                        
                                        combined_df = pd.concat([train_df, test_df])
                                        
                                        fig = px.box(
                                            combined_df, x='dataset', y=tgt_col,
                                            title="Распределение целевой переменной по выборкам"
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Ошибка при разделении данных: {e}")
                            logging.error(f"Ошибка при разделении данных: {e}")
        else:
            st.error(f"Не удалось найти колонку {dt_col} для разделения данных")
        
        # Кнопки для использования разделенных данных
        if "train_df" in st.session_state and "test_df" in st.session_state:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Использовать обучающую выборку для анализа", key="use_train_analysis_btn"):
                    st.session_state["df_analysis"] = st.session_state["train_df"]
                    st.success("Теперь для анализа используется обучающая выборка!")
                
                if st.button("Использовать обучающую выборку на главной", key="use_train_main_btn"):
                    st.session_state["df"] = st.session_state["train_df"]
                    st.success("Теперь на главной странице используется обучающая выборка!")
            
            with col2:
                if st.button("Использовать тестовую выборку для анализа", key="use_test_analysis_btn"):
                    st.session_state["df_analysis"] = st.session_state["test_df"]
                    st.success("Теперь для анализа используется тестовая выборка!")
                
                if st.button("Использовать тестовую выборку на главной", key="use_test_main_btn"):
                    st.session_state["df"] = st.session_state["test_df"]
                    st.success("Теперь на главной странице используется тестовая выборка!")
        
        # После разделения данных добавляем кнопки для экспорта
        if "train_df" in st.session_state and "test_df" in st.session_state:
            st.subheader("Экспорт разделенных данных")
            
            # Экспорт обучающей выборки
            st.write("#### Обучающая выборка")
            download_excel(st.session_state["train_df"], "train_data.xlsx")
            
            # Экспорт тестовой выборки
            st.write("#### Тестовая выборка")
            download_excel(st.session_state["test_df"], "test_data.xlsx")
            
            # Экспорт валидационной выборки, если она есть
            if st.session_state.get("val_df") is not None:
                st.write("#### Валидационная выборка")
                download_excel(st.session_state["val_df"], "validation_data.xlsx")
            
            # Информация о том, как использовать разделенные данные
            st.info("""
            **Как использовать разделенные данные:**
            
            1. **Обучающая выборка** используется для обучения моделей
            2. **Валидационная выборка** используется для настройки гиперпараметров
            3. **Тестовая выборка** используется для финальной оценки модели
            
            Вы можете:
            - Выгрузить каждую выборку в Excel для использования в других инструментах
            - Использовать любую из выборок для анализа или как основной датасет на главной странице
            - Разделение важно для правильной оценки моделей и предотвращения переобучения
            """)
    
    # Добавляем общий информационный блок в конце страницы
    st.sidebar.subheader("🔍 О работе с данными")
    st.sidebar.info("""
    **Важно понимать:**
    
    1. Все изменения данных (очистка выбросов, генерация признаков и т.д.) 
       при нажатии кнопки "Использовать..." применяются только для текущего анализа.
       
    2. Чтобы использовать модифицированные данные для обучения моделей, 
       нажмите кнопку "Использовать ... на главной странице".
       
    3. Для сохранения результатов используйте кнопки "Выгрузить в Excel".
    
    4. Вы всегда можете вернуться к исходным данным, загрузив их заново.
    """)