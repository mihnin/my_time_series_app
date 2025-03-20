# app_ui.py
import streamlit as st
import yaml
import os
import pandas as pd
import plotly.express as px
import psutil
import gc
import logging
from typing import Dict, Any, Optional

from src.data.data_processing import load_data, show_dataset_stats
from src.data.auto_detect import detect_column_names, detect_frequency
from src.config.app_config import get_config

CONFIG_PATH = "config/config.yaml"

def load_config(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл конфигурации {path} не найден.")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    metrics_dict = data.get("metrics_dict", {})
    ag_models = data.get("ag_models", {})
    return metrics_dict, ag_models

METRICS_DICT, AG_MODELS = load_config(CONFIG_PATH)
metrics_list = list(METRICS_DICT.keys())
presets_list = ["fast_training", "medium_quality", "high_quality", "best_quality"]
all_models_opt = "* (все)"
autoGluon_models = [
    'DeepAR', 'ARIMA', 'AutoARIMA', 'AutoETS', 'ETS', 'Theta', 
    'DirectTabular', 'RecursiveTabular', 'NPTS', 'PatchTST', 
    'DLinear', 'TiDE', 'TemporalFusionTransformer', 'Naive', 
    'SeasonalNaive', 'Average', 'SeasonalAverage', 'Chronos'
]
model_options = [all_models_opt] + autoGluon_models

# Зададим соответствие между базовыми значениями частоты и полными описаниями
FREQ_MAPPING = {
    "auto": "auto (угадать)",
    "D": "D (день)",
    "h": "h (час)",
    "H": "H (час)",
    "M": "M (месяц)",
    "B": "B (рабочие дни)",
    "W": "W (неделя)",
    "Q": "Q (квартал)",
    "Y": "Y (год)"
}

# Обратное отображение для получения базового значения из полного описания
FREQ_REVERSE_MAPPING = {v: k for k, v in FREQ_MAPPING.items()}

def get_base_freq(freq_display):
    """
    Извлекает базовое значение частоты из отображаемого значения
    
    Параметры
    ---------
    freq_display : str
        Отображаемое значение частоты, например "D (день)"
    
    Возвращает
    ----------
    str
        Базовое значение частоты, например "D"
    """
    # Если freq_display уже базовое значение, вернуть его
    if freq_display in FREQ_MAPPING:
        return freq_display
        
    # Если freq_display есть в обратном маппинге, используем его
    if freq_display in FREQ_REVERSE_MAPPING:
        return FREQ_REVERSE_MAPPING[freq_display]
    
    # Иначе извлекаем значение до пробела или скобки
    if " " in freq_display:
        return freq_display.split(" ")[0]
    if "(" in freq_display:
        return freq_display.split("(")[0].strip()
    
    # Возвращаем исходное значение, если не удалось распознать
    return freq_display

def auto_select_fields(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Автоматически определяет колонки даты, ID и target на основе данных
    
    Parameters:
    -----------
    df : pd.DataFrame
        Датафрейм с данными
        
    Returns:
    --------
    Dict[str, str]
        Словарь с определенными полями
    """
    config = get_config()
    auto_detection_enabled = config.get('auto_detection', {}).get('fields_enabled', True)
    
    if not auto_detection_enabled:
        return {}
    
    try:
        # Определяем колонки
        detected_fields = detect_column_names(df)
        
        # Проверяем, что полученные значения не являются pandas Series
        for key in ['dt_col', 'id_col', 'tgt_col']:
            if key in detected_fields and isinstance(detected_fields[key], pd.Series):
                # Если это Series и содержит одно значение, берем первый элемент
                if len(detected_fields[key]) == 1:
                    detected_fields[key] = detected_fields[key].iloc[0]
                else:
                    # Иначе используем наиболее подходящее значение или None
                    logging.warning(f"Поле {key} содержит множество значений, берем первое")
                    detected_fields[key] = detected_fields[key].iloc[0] if not detected_fields[key].empty else None
        
        # Устанавливаем значение частоты по умолчанию - 'D (день)'
        detected_fields['freq'] = "D (день)"
        
        logging.info(f"Автоматически определены поля: {detected_fields}")
        return detected_fields
    
    except Exception as e:
        logging.error(f"Ошибка при автоматическом определении полей: {e}")
        return {}

def display_error_message(error_text, title="Ошибка"):
    """Отображает красивое сообщение об ошибке"""
    st.error(f"**{title}**: {error_text}")
    
    # Добавляем специальную обработку для известных ошибок
    if "list index out of range" in error_text:
        st.warning("""
        **Возможная причина**: проблема с выбором моделей.
        
        **Рекомендации**:
        1. Выберите "* (все)" для использования всех доступных моделей
        2. Или выберите конкретные модели из списка
        3. Или используйте preset с указанным качеством обучения
        """)
    elif "time_limit must be positive" in error_text:
        st.warning("""
        **Возможная причина**: некорректное значение времени обучения.
        
        **Рекомендации**:
        1. Установите положительное значение времени обучения (например, 60 секунд)
        """)
    elif "invalid frequency" in error_text.lower():
        st.warning("""
        **Возможная причина**: неподдерживаемая частота временного ряда.
        
        **Рекомендации**:
        1. Используйте одну из стандартных частот (D, W, M, Q, Y)
        2. Убедитесь, что данные имеют равномерную периодичность
        """)

def setup_ui():
    st.markdown("### Версия 2.0")
    st.title("Бизнес-приложение для прогнозирования временных рядов")
    
    # Восстанавливаем сохраненные значения после перезагрузки
    if "_saved_use_holidays" in st.session_state:
        st.session_state["use_holidays_key"] = st.session_state["_saved_use_holidays"]
        del st.session_state["_saved_use_holidays"]
        
    if "_saved_static_feats" in st.session_state:
        st.session_state["static_feats_key"] = st.session_state["_saved_static_feats"]
        del st.session_state["_saved_static_feats"]
        
    if "_saved_page" in st.session_state:
        st.session_state["page_choice"] = st.session_state["_saved_page"]
        del st.session_state["_saved_page"]
    
    # Убираем админку из списка страниц, оставляем только основные
    pages = ["Главная", "Анализ данных", "Help"]
    page_choice = st.sidebar.selectbox("Навигация", pages, key="page_choice")
    
    # Инициализация session_state
    session_keys = [
        "df", "predictor", "leaderboard", "predictions", "fit_summary",
        "static_df_train", "static_df_fore", "best_model_name", "best_model_score",
        "df_forecast", "metric_key", "presets_key", "models_key"
    ]
    for key in session_keys:
        if key not in st.session_state:
            if key == "metric_key":
                st.session_state[key] = metrics_list[0]
            elif key == "presets_key":
                st.session_state[key] = "best_quality"
            elif key == "models_key":
                st.session_state[key] = [all_models_opt]
            else:
                st.session_state[key] = None
    
    if "df_forecast" in st.session_state:
        del st.session_state["df_forecast"]
    if "static_df_fore" in st.session_state:
        del st.session_state["static_df_fore"]
    
    # Если выбрана страница анализа данных или справки, не отображаем остальные элементы UI
    if page_choice in ["Анализ данных", "Help"]:
        return page_choice
    
    # ========== (1) Загрузка данных ==========
    st.sidebar.header("1. Загрузка данных")
    
    # Опциональные настройки загрузки для больших файлов
    with st.sidebar.expander("Настройки для больших файлов"):
        chunk_size = st.number_input(
            "Размер чанка (строк)",
            min_value=1000,
            max_value=1000000,
            value=100000,
            step=10000,
            help="Для больших файлов (>100 МБ) данные будут загружаться частями. Задайте размер каждой части."
        )
    
    train_file = st.sidebar.file_uploader("Train (обязательно)", type=["csv", "xls", "xlsx"], key="train_file_uploader")
    if st.sidebar.button("📂 Загрузить данные", key="load_data_btn"):
        if not train_file:
            st.error("Train-файл обязателен!")
        else:
            try:
                with st.spinner("Загрузка данных..."):
                    df_train = load_data(train_file, chunk_size=chunk_size)
                    st.session_state["df"] = df_train
                    st.success(f"Train-файл загружен! Строк: {len(df_train)}, колонок: {len(df_train.columns)}")
                    
                    # Автоматическое определение полей
                    auto_detected = auto_select_fields(df_train)
                    
                    # Применяем автоматически определенные поля
                    if auto_detected:
                        if auto_detected.get('dt_col'):
                            st.session_state["dt_col_key"] = auto_detected['dt_col']
                        
                        if auto_detected.get('id_col'):
                            st.session_state["id_col_key"] = auto_detected['id_col']
                        
                        if auto_detected.get('tgt_col'):
                            st.session_state["tgt_col_key"] = auto_detected['tgt_col']
                        
                        if auto_detected.get('freq'):
                            st.session_state["freq_key"] = auto_detected['freq']
                        
                        st.info("Автоматически определены поля:\n" +
                               f"- Дата: {auto_detected.get('dt_col', '<не определено>')}\n" +
                               f"- ID: {auto_detected.get('id_col', '<не определено>')}\n" +
                               f"- Target: {auto_detected.get('tgt_col', '<не определено>')}\n" +
                               f"- Частота: {auto_detected.get('freq', '<не определено>')}")
                    
                    # Копируем в session_state для последующего использования
                    st.session_state["df"] = df_train
                    
                    # Для больших датафреймов используем выборку при отображении
                    if len(df_train) > 1000:
                        # Отображаем датафрейм на всю ширину экрана с горизонтальной прокруткой
                        st.dataframe(
                            df_train.head(1000),
                            use_container_width=True,
                            height=500
                        )
                        st.info(f"Показаны первые 1000 из {len(df_train)} строк.")
                    else:
                        # Отображаем весь датафрейм на всю ширину экрана
                        st.dataframe(
                            df_train,
                            use_container_width=True,
                            height=500
                        )
                    
                    st.subheader("Статистика Train")
                    show_dataset_stats(df_train)
                    
                    # Освобождаем память, если её мало
                    memory_usage = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024 * 1024)  # в ГБ
                    if memory_usage > 1.5:  # если используется больше 1.5 ГБ
                        gc.collect()
                        
                    # Создаем локальную копию для расчетов и освобождаем оригинал
                    df_train_local = None
                    gc.collect()
            except Exception as e:
                st.error(f"Ошибка загрузки: {e}")
                
                # Освобождаем память после ошибки
                gc.collect()
    
    # ========== (2) Настройка колонок ==========
    st.sidebar.header("2. Колонки датасета")
    df_current = st.session_state.get("df")
    all_cols = list(df_current.columns) if df_current is not None else []
    
    if "dt_col_key" not in st.session_state:
        st.session_state["dt_col_key"] = "<нет>"
    if "tgt_col_key" not in st.session_state:
        st.session_state["tgt_col_key"] = "<нет>"
    if "id_col_key" not in st.session_state:
        st.session_state["id_col_key"] = "<нет>"
    
    dt_stored = st.session_state["dt_col_key"]
    tgt_stored = st.session_state["tgt_col_key"]
    id_stored = st.session_state["id_col_key"]
    
    if dt_stored not in ["<нет>"] + all_cols:
        st.session_state["dt_col_key"] = "<нет>"
    if tgt_stored not in ["<нет>"] + all_cols:
        st.session_state["tgt_col_key"] = "<нет>"
    if id_stored not in ["<нет>"] + all_cols:
        st.session_state["id_col_key"] = "<нет>"
    
    # Код проверки временных значений удален, так как значения устанавливаются напрямую
    # при автоопределении полей
    
    dt_col = st.sidebar.selectbox("Колонка с датой", ["<нет>"] + all_cols, key="dt_col_key")
    tgt_col = st.sidebar.selectbox("Колонка target", ["<нет>"] + all_cols, key="tgt_col_key")
    id_col = st.sidebar.selectbox("Колонка ID (категориальный)", ["<нет>"] + all_cols, key="id_col_key")
    
    # Кнопка автоматического определения полей
    if df_current is not None and st.sidebar.button("🔍 Автоопределение полей", key="auto_detect_fields_btn"):
        auto_detected = auto_select_fields(df_current)
        if auto_detected:
            # Напрямую устанавливаем значения в session_state для ключей виджетов
            # вместо использования временных переменных и перезагрузки
            changed = False
            
            if auto_detected.get('dt_col'):
                st.session_state["dt_col_key"] = auto_detected['dt_col']
                changed = True
            
            if auto_detected.get('id_col'):
                st.session_state["id_col_key"] = auto_detected['id_col']
                changed = True
            
            if auto_detected.get('tgt_col'):
                st.session_state["tgt_col_key"] = auto_detected['tgt_col']
                changed = True
            
            if auto_detected.get('freq'):
                st.session_state["freq_key"] = auto_detected['freq']
                changed = True
            
            st.sidebar.success("Автоматически определены поля!")
            
            # Сохраняем состояние дополнительных виджетов, которые могут быть потеряны при перезагрузке
            if "use_holidays_key" in st.session_state:
                use_holidays_value = st.session_state["use_holidays_key"]
                st.session_state["_saved_use_holidays"] = use_holidays_value
                
            if "static_feats_key" in st.session_state:
                static_feats_value = st.session_state["static_feats_key"]
                st.session_state["_saved_static_feats"] = static_feats_value
                
            # Только если действительно что-то изменилось, выполняем перезагрузку
            if changed:
                st.rerun()
        else:
            st.sidebar.warning("Не удалось автоматически определить поля")
    
    # Статические признаки
    st.sidebar.header("Статические признаки (до 3)")
    if "static_feats_key" not in st.session_state:
        st.session_state["static_feats_key"] = []
    existing_static_feats = st.session_state["static_feats_key"]
    possible_static = [c for c in all_cols if c not in [dt_col, tgt_col, id_col, "<нет>"]]
    filtered_feats = [feat for feat in existing_static_feats if feat in possible_static]
    if len(filtered_feats) != len(existing_static_feats):
        st.session_state["static_feats_key"] = filtered_feats
    
    static_feats = st.sidebar.multiselect("Статические колонки:", possible_static, key="static_feats_key")
    
    if "use_holidays_key" not in st.session_state:
        st.session_state["use_holidays_key"] = False
    st.sidebar.checkbox("Учитывать праздники РФ?", value=st.session_state["use_holidays_key"], key="use_holidays_key")
    
    # ========== (3) Обработка пропусков ==========
    st.sidebar.header("3. Обработка пропусков")
    # Заменить существующий selectbox для fill_method более информативным
    fill_options = [
        "None (оставить как есть)", 
        "Constant=0 (заменить на нули)", 
        "Group mean (среднее по группе)", 
        "Forward fill (протянуть значения)", 
        "Interpolate (линейная интерполяция)", 
        "KNN imputer (k ближайших соседей)"
    ]
    fill_map = {opt: opt.split(" ")[0] for opt in fill_options}
    selected_fill = st.sidebar.selectbox(
        "Способ заполнения пропусков", 
        fill_options, 
        key="fill_method_display"
    )
    st.session_state["fill_method_key"] = fill_map[selected_fill]
    
    if "group_cols_for_fill_key" not in st.session_state:
        st.session_state["group_cols_for_fill_key"] = []
    st.sidebar.multiselect("Колонки для группировки", static_feats, key="group_cols_for_fill_key")
    
    # ========== (4) Частота (freq) ==========
    st.sidebar.header("4. Частота (freq)")
    
    # Получаем список доступных частот без авто-определения
    freq_options = ["D (день)", "h (час)", "M (месяц)", "B (рабочие дни)", "W (неделя)", "Q (квартал)"]

    if "freq_key" not in st.session_state:
        st.session_state["freq_key"] = "M (месяц)"  # Меняем значение по умолчанию на 'M (месяц)'

    # Проверяем, что значение freq_key есть в списке опций
    current_freq = st.session_state["freq_key"]
    if current_freq not in freq_options:
        # Если текущее значение - 'auto (угадать)', меняем на 'M (месяц)'
        if current_freq == "auto (угадать)":
            st.session_state["freq_key"] = "M (месяц)"
        else:
            # Проверяем базовое значение частоты
            for opt in freq_options:
                # Извлекаем базовое значение частоты (до пробела)
                base_freq = opt.split(" ")[0]
                if current_freq == base_freq or current_freq.startswith(base_freq):
                    st.session_state["freq_key"] = opt
                    break
            
            # Если соответствие не найдено, используем M (месяц) по умолчанию
            if current_freq not in freq_options:
                st.session_state["freq_key"] = "M (месяц)"

    # Выбор частоты (без кнопки автоопределения)
    freq_selection = st.sidebar.selectbox("Частота данных", freq_options, 
                                       index=freq_options.index(st.session_state["freq_key"]), 
                                       key="freq_key")
    
    # ========== (5) Метрика и модели ==========
    st.sidebar.header("5. Выбор моделей")
    
    # Получаем список доступных моделей AutoGluon
    autoGluon_models = [
        'DeepAR', 'ARIMA', 'AutoARIMA', 'AutoETS', 'ETS', 'Theta', 
        'DirectTabular', 'RecursiveTabular', 'NPTS', 'PatchTST', 
        'DLinear', 'TiDE', 'TemporalFusionTransformer', 'Naive', 
        'SeasonalNaive', 'Average', 'SeasonalAverage', 'Chronos'
    ]
    
    # Создаем список опций, начиная с "Все модели"
    model_options = [all_models_opt] + autoGluon_models
    
    # Выбор моделей
    if "models_key" not in st.session_state:
        st.session_state["models_key"] = [all_models_opt]
    
    st.sidebar.multiselect("Модели AutoGluon", model_options, key="models_key")
    st.sidebar.selectbox("Метрика", metrics_list, index=metrics_list.index(st.session_state["metric_key"]), key="metric_key")
    st.sidebar.selectbox("Presets", presets_list, index=presets_list.index(st.session_state["presets_key"]), key="presets_key")
    st.sidebar.number_input(
        "prediction_length", 
        1, 365, 2, 
        key="prediction_length_key",
        help="Горизонт прогноза (количество точек в будущем). Модель будет обучена предсказывать именно на это количество шагов вперед."
    )
    
    st.sidebar.number_input(
        "time_limit (sec)", 
        10, 36000, 600, 
        key="time_limit_key",
        help="Максимальное время (в секундах) для обучения всех моделей. Чем больше времени, тем лучше результат, но медленнее обучение."
    )
    
    st.sidebar.checkbox(
        "Прогнозировать только среднее (mean)?", 
        value=st.session_state.get("mean_only_key", False), 
        key="mean_only_key",
        help="Если включено, модель будет предсказывать только среднее значение (0.5 квантиль). Если выключено, будут предсказаны все квантили (0.1, 0.5, 0.9), что даст интервалы неопределенности."
    )
    
    # Предварительный график
    if df_current is not None and dt_col != "<нет>" and tgt_col != "<нет>":
        try:
            with st.spinner("Построение графика..."):
                df_plot = df_current.copy()
                
                # Для больших датафреймов используем выборку при построении графика
                if len(df_plot) > 10000:
                    st.info(f"Для графика используется выборка из 10000 точек (из {len(df_plot)} строк).")
                    # Если есть ID, берем по несколько ID
                    if id_col != "<нет>":
                        ids = df_plot[id_col].unique()
                        if len(ids) > 10:
                            selected_ids = ids[:10]  # Берем первые 10 ID
                            df_plot = df_plot[df_plot[id_col].isin(selected_ids)]
                        
                        # Если все еще слишком много точек
                        if len(df_plot) > 10000:
                            df_plot = df_plot.sample(10000, random_state=42)
                    else:
                        df_plot = df_plot.sample(10000, random_state=42)
                
                # Правильное преобразование дат с использованием dayfirst=False
                df_plot[dt_col] = pd.to_datetime(df_plot[dt_col], errors="coerce", format=None, dayfirst=False)
                df_plot = df_plot.dropna(subset=[dt_col])
                
                if id_col != "<нет>":
                    fig_target = px.line(df_plot.sort_values(dt_col), x=dt_col, y=tgt_col, color=id_col, title="График Target по ID")
                else:
                    fig_target = px.line(df_plot.sort_values(dt_col), x=dt_col, y=tgt_col, title="График Target (без ID)")
                
                fig_target.update_layout(height=400)
                st.subheader("Предварительный анализ Target")
                st.plotly_chart(fig_target, use_container_width=True)
                
                # Освобождаем память
                del df_plot
                gc.collect()
        except Exception as e:
            st.warning(f"Не удалось построить график: {e}")
    
    # ========== (6) Обучение модели ==========
    st.sidebar.header("6. Обучение модели")
    st.sidebar.checkbox("Обучение, Прогноз и Сохранение", key="train_predict_save_checkbox", value=False)

    # Стилизуем кнопки: красная для обучения, голубые для остальных
    button_css = """
    <style>
    /* Общий стиль для всех кнопок - одинаковая ширина */
    div[data-testid="stButton"] button {
        width: 100%;
    }

    /* Стиль для кнопки обучения модели (красная с белым текстом) */
    div[data-testid="stButton"] button[kind="secondary"][data-testid="StyledFullScreenButton"] {
        background-color: #E53935;
        color: white;
    }

    /* Стиль для всех остальных кнопок (голубые) */
    div[data-testid="stButton"] button[kind="secondary"]:not([data-testid="StyledFullScreenButton"]) {
        background-color: #2196F3;
        color: white;
    }
    </style>
    """
    st.sidebar.markdown(button_css, unsafe_allow_html=True)

    # Красная кнопка на всю ширину
    if st.sidebar.button("🚀 Обучить модель", key="fit_model_btn", help="Нажмите для запуска обучения модели", type="primary", use_container_width=True):
        # Нужно импортировать run_training непосредственно здесь, иначе будет циклический импорт
        from app_training import run_training
        st.sidebar.success("Кнопка нажата! Запуск обучения из сайдбара...")
        
        # Проверяем наличие необходимых данных перед запуском обучения
        if st.session_state.get("df") is None:
            st.error("❌ Ошибка: Датасет не загружен. Пожалуйста, загрузите датасет.")
            return
        
        dt_col = st.session_state.get("dt_col_key")
        tgt_col = st.session_state.get("tgt_col_key")
        id_col = st.session_state.get("id_col_key")
        
        if dt_col == "<нет>" or tgt_col == "<нет>":
            st.error("❌ Ошибка: Не выбраны обязательные колонки (дата и target).")
            return
            
        # Получаем горизонт прогнозирования
        prediction_length = st.session_state.get("prediction_length_key", 10)
        
        # Получаем базовую частоту из отображаемого значения
        freq_display = st.session_state.get("freq_key", "auto (угадать)")
        
        # Получаем выбранные модели
        models_key = st.session_state.get("models_key", [])
        
        # Получаем выбранную метрику
        metric_key = st.session_state.get("metric_key", "RMSE")
        
        # Вызываем функцию с необходимыми аргументами
        try:
            run_training(
                df_train=st.session_state["df"],
                dt_col=dt_col,
                tgt_col=tgt_col,
                horizon=prediction_length,
                id_col=id_col if id_col != "<нет>" else None,
                freq=freq_display,
                models=models_key,
                eval_metric=metric_key,
                time_limit=st.session_state.get("time_limit_key", 300),
                use_chronos=True,
                chronos_model="bolt_small"
            )
        except Exception as e:
            display_error_message(str(e), title="Ошибка обучения модели")
    
    # ========== (7) Прогноз ==========
    st.sidebar.header("7. Прогноз")
    
    # Проверка, есть ли модель
    predictor_exists = st.session_state.get("predictor") is not None
    
    if predictor_exists:
        if st.sidebar.button("📊 Сделать прогноз", key="predict_btn", use_container_width=True):
            # Прямой вызов функции прогнозирования
            from app_prediction import run_prediction
            st.sidebar.success("Кнопка нажата! Запуск прогнозирования из сайдбара...")
            run_prediction()
    else:
        st.sidebar.warning("Сначала обучите модель")
    
    # Логи обучения/прогноза
    if st.session_state.get("fit_summary") is not None:
        with st.expander("Результаты обучения", expanded=False):
            st.json(st.session_state["fit_summary"])

    if st.session_state.get("leaderboard") is not None:
        with st.expander("Лидерборд моделей", expanded=False):
            st.dataframe(st.session_state["leaderboard"])
            
            # Проверяем, является ли лучшая модель ансамблевой
            if 'leaderboard' in st.session_state and not st.session_state['leaderboard'].empty:
                try:
                    # Пытаемся получить имя лучшей модели
                    predictor = st.session_state.get('predictor')
                    if predictor:
                        # Используем property model_best вместо доступа через лидерборд
                        best_model_name = predictor.model_best if hasattr(predictor, 'model_best') else predictor.get_model_best()
                    else:
                        # Если предиктора нет, берем из лидерборда
                        best_model_name = st.session_state['leaderboard'].iloc[0]['model']
                    
                    if 'Ensemble' in best_model_name:
                        st.info("🔄 Лучшая модель - ансамблевая (Weighted Ensemble).")
                        
                        # Пробуем получить информацию о составе ансамбля
                        predictor = st.session_state.get('predictor')
                        if predictor:
                            from src.utils.exporter import extract_ensemble_weights
                            ensemble_weights, model_details = extract_ensemble_weights(predictor)
                            
                            if ensemble_weights is not None and not ensemble_weights.empty:
                                st.subheader("📊 Состав ансамблевой модели")
                                
                                # Преобразуем веса в проценты для лучшей читаемости
                                if 'Вес' in ensemble_weights.columns:
                                    ensemble_weights['Вес (%)'] = (ensemble_weights['Вес'] * 100).round(2)
                                    ensemble_weights = ensemble_weights.sort_values('Вес (%)', ascending=False)
                                
                                # Создаем столбчатую диаграмму для визуализации весов
                                fig = px.bar(
                                    ensemble_weights, 
                                    x='Модель', 
                                    y='Вес (%)', 
                                    title='Вклад моделей в ансамбль',
                                    color='Вес (%)',
                                    color_continuous_scale='Viridis'
                                )
                                fig.update_layout(height=400)
                                st.plotly_chart(fig, use_container_width=True)
                            
                                # Отображаем таблицу с весами моделей
                                st.subheader("📋 Таблица весов моделей")
                                st.dataframe(ensemble_weights)
                                
                                # Если есть детальная информация о моделях, отображаем ее
                                if model_details is not None and not model_details.empty:
                                    with st.expander("Детальная информация о моделях в ансамбле"):
                                        st.dataframe(model_details)
                                
                                # Освобождаем память после работы с данными ансамбля
                                del ensemble_weights
                                if model_details is not None:
                                    del model_details
                                gc.collect()
                            else:
                                st.warning("⚠️ Не удалось получить информацию о составе ансамблевой модели.")
                                st.info("Подробная информация об ансамбле будет доступна в Excel при экспорте результатов.")
                except Exception as e:
                    st.warning(f"Не удалось получить информацию о составе ансамблевой модели: {e}")
    
    # ========== (8) Сохранение результатов ==========
    st.sidebar.header("8. Сохранение результатов прогноза")
    # Используем другой ключ для session_state, не совпадающий с ключом виджета
    st.sidebar.button("💾 Сохранить результаты в Excel", key="save_excel_btn", on_click=lambda: st.session_state.update({"excel_save_clicked": True}), use_container_width=True)

    # ========== (9) Логи приложения ==========
    st.sidebar.header("9. Логи приложения")
    log_col1, log_col2 = st.sidebar.columns(2)
    log_col1.button("👁️ Показать логи", key="show_logs_btn", on_click=lambda: st.session_state.update({"logs_show_clicked": True}), use_container_width=True)
    log_col2.button("📥 Скачать логи", key="download_logs_btn", on_click=lambda: st.session_state.update({"logs_download_clicked": True}), use_container_width=True)
    st.sidebar.button("🧹 Очистить логи", key="clear_logs_btn", on_click=lambda: st.session_state.update({"logs_clear_clicked": True}), use_container_width=True)

    # ========== (10) Выгрузка моделей и логов ==========
    st.sidebar.header("10. Выгрузка моделей и логов")
    st.sidebar.button("📦 Скачать архив (модели + логи)", key="download_model_and_logs", on_click=lambda: st.session_state.update({"model_download_clicked": True}), use_container_width=True)
    
    return page_choice