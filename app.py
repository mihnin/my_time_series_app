import streamlit as st
import plotly.express as px
import sys
import os

from data_processing import load_data, convert_to_timeseries
from forecasting import make_timeseries_dataframe, train_model, forecast
from utils import setup_logger, save_model, load_model, read_logs, MODEL_PATH

import pandas as pd
import logging

# (Опционально) проверка активации conda-окружения
if not os.path.exists(os.path.join(sys.prefix, 'conda-meta')):
    st.warning("⚠️ Conda окружение не активировано! Запустите команду:")
    st.code("conda activate my_time_series_app")

# Инициализация логов при запуске
setup_logger()

# Мы используем Streamlit "Pages" для организации Help-страницы или делаем один файл — ниже используем один файл
def show_help_page():
    st.title("Справка / Помощь")
    st.markdown("""
    **Что загружать в приложение?**  
    - Файл должен содержать как минимум три колонки:  
      1) Идентификатор временного ряда (по умолчанию `item_id`).  
      2) Метку времени (по умолчанию `timestamp`).  
      3) Целевой признак (по умолчанию `target`).  

    **Поддерживаемые форматы:**  
    - CSV (`.csv`)  
    - Excel (`.xls`, `.xlsx`)

    **Структура данных:**  
    - Колонка с ID ряда (например, `item_id`) обозначает разные временные ряды.  
    - Колонка с датой/временем (например, `timestamp`) должна быть в формате, распознаваемом `pandas.to_datetime()`.  
    - Колонка с целевым признаком (`target`) содержит величину, которую вы хотите прогнозировать.  

    **Примечания:**  
    - Если есть пропущенные значения в столбце `target`, они заполняются медианой по каждой группе `item_id`.  
    - Дубликаты по (item_id, timestamp) не допускаются.  
    - Некорректные даты (не преобразуемые в datetime) будут вызывать ошибку.  
    - Если у вас есть дополнительные столбцы, они будут проигнорированы либо используются как ковариаты (если указать).  

    **Пример структуры CSV** (минимальный):
    ```
    item_id,timestamp,target
    H1,2023-01-01 00:00:00,123
    H1,2023-01-01 01:00:00,150
    H2,2023-01-01 00:00:00,999
    ...
    ```
    """)

def main():
    # Создаём меню выбора страниц (2 вкладки): "Главная" и "Help"
    page_options = ["Главная", "Help"]
    page_choice = st.sidebar.selectbox("Навигация", page_options)

    if page_choice == "Help":
        show_help_page()
        return

    # Иначе продолжаем отрисовывать Главную страницу
    st.title("Бизнес-приложение для прогноза временных рядов (AutoGluon)")

    # 1. Загрузка данных
    st.sidebar.header("1. Загрузка данных")
    uploaded_file = st.sidebar.file_uploader(
        "Загрузите CSV или Excel-файл",
        type=["csv", "xls", "xlsx"]
    )

    # 2. Настройки обучения
    st.sidebar.header("2. Настройки обучения")
    id_col = st.sidebar.text_input("Столбец ID серии", value="item_id")
    timestamp_col = st.sidebar.text_input("Столбец даты/времени", value="timestamp")
    target_col = st.sidebar.text_input("Целевой столбец", value="target")

    prediction_length = st.sidebar.number_input(
        "Длина прогноза (prediction_length)",
        min_value=1, max_value=365, value=30
    )
    time_limit = st.sidebar.number_input(
        "Лимит времени на обучение (в секундах)",
        min_value=10, max_value=36000, value=60
    )
    presets = st.sidebar.selectbox(
        "Выберите пресет (пакет настроек)",
        ["fast_quality", "medium_quality", "high_quality", "best_quality"],
        index=1
    )
    eval_metric = st.sidebar.selectbox(
        "Метрика для оценки",
        ["MASE", "sMAPE", "RMSE", "CRPS", "MQAPE"],
        index=0
    )

    known_covariates = st.sidebar.text_input(
        "Колонки, известные в будущем (через запятую)",
        value=""
    )
    if known_covariates.strip():
        known_covariates_list = [col.strip() for col in known_covariates.split(",")]
    else:
        known_covariates_list = []

    # Храним состояния
    if "df" not in st.session_state:
        st.session_state["df"] = None
    if "predictor" not in st.session_state:
        st.session_state["predictor"] = None
    if "leaderboard" not in st.session_state:
        st.session_state["leaderboard"] = None
    if "predictions" not in st.session_state:
        st.session_state["predictions"] = None
    if "fit_summary" not in st.session_state:
        st.session_state["fit_summary"] = None

    # 3. Кнопка: Загрузить данные
    if st.sidebar.button("Загрузить данные"):
        if not uploaded_file:
            st.error("Файл не выбран. Пожалуйста, загрузите CSV или Excel.")
        else:
            try:
                df = load_data(uploaded_file)
                st.session_state["df"] = df
                st.success("Данные успешно загружены!")

                st.subheader("Предварительный просмотр данных")
                st.write(df.head())

                # Пробуем визуализировать
                if timestamp_col in df.columns and target_col in df.columns:
                    fig = px.line(
                        df,
                        x=timestamp_col,
                        y=target_col,
                        title="Исходный временной ряд"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Ошибка при загрузке данных: {e}")
                logging.error(str(e))

    # 4. Кнопка: Обучить модель
    if st.sidebar.button("Обучить модель"):
        if st.session_state["df"] is None:
            st.warning("Сначала загрузите данные.")
        else:
            df = st.session_state["df"]
            try:
                df_prepared = convert_to_timeseries(df, id_col, timestamp_col, target_col)
                train_ts_df = make_timeseries_dataframe(df_prepared)

                predictor = train_model(
                    train_ts_df,
                    target="target",
                    prediction_length=prediction_length,
                    time_limit=time_limit,
                    presets=presets,
                    eval_metric=eval_metric,
                    known_covariates=known_covariates_list
                )
                st.session_state["predictor"] = predictor
                st.success("Модель успешно обучена!")

                # Лидерборд
                leaderboard_df = predictor.leaderboard(train_ts_df)
                st.session_state["leaderboard"] = leaderboard_df
                st.subheader("Лидерборд моделей")
                st.dataframe(leaderboard_df)

                # Получаем fit_summary (строка с информацией об обучении, лучшей модели и т.д.)
                summary_text = predictor.fit_summary()
                st.session_state["fit_summary"] = summary_text

                # Отображаем короткое сообщение:
                # 1) Какая модель лучшая
                # 2) Какой у неё скор
                # Если нужно извлечь из leaderboard_df:
                best_model = leaderboard_df.iloc[0]['model']
                best_score = leaderboard_df.iloc[0]['score_val']
                st.info(f"**Лучший результат показала модель:** {best_model}\n\n**C оценкой (score_val):** {best_score}")

                # Также выведем "summary_text" (включая системную информацию и прочие детали)
                with st.expander("Подробная информация о ходе обучения (fit_summary)"):
                    st.text(summary_text)

            except Exception as e:
                st.error(f"Ошибка при обучении: {e}")
                logging.error(str(e))

    # 5. Прогноз
    st.sidebar.header("3. Прогнозирование")
    if st.sidebar.button("Сделать прогноз"):
        if st.session_state["predictor"] is None:
            st.warning("Сначала обучите модель.")
        else:
            df = st.session_state["df"]
            predictor = st.session_state["predictor"]
            try:
                df_prepared = convert_to_timeseries(df, id_col, timestamp_col, target_col)
                ts_df = make_timeseries_dataframe(df_prepared)
                preds = forecast(
                    predictor,
                    ts_df,
                    known_covariates=known_covariates_list
                )
                st.session_state["predictions"] = preds
                st.subheader("Прогноз")

                preds_df = preds.reset_index()  # item_id и timestamp в колонки
                st.write(preds_df.head())

                # Медиана, если есть 0.5
                if "0.5" in preds_df.columns:
                    fig_pred = px.line(
                        preds_df,
                        x="timestamp",
                        y="0.5",
                        color="item_id",
                        title="Медианный прогноз (квантиль 0.5)"
                    )
                    st.plotly_chart(fig_pred, use_container_width=True)
                else:
                    st.warning("В предсказании нет колонки '0.5'. Попробуйте другую кванть или 'mean', если модель её генерирует.")

            except Exception as e:
                st.error(f"Ошибка при прогнозировании: {e}")
                logging.error(str(e))

    # 6. Сохранение результатов (в Excel)
    st.sidebar.header("4. Сохранение результатов")
    save_path = st.sidebar.text_input(
        "Укажите путь для сохранения результатов (Excel)",
        value="results.xlsx"
    )
    if st.sidebar.button("Сохранить результаты в Excel"):
        if st.session_state["df"] is None:
            st.warning("Сначала загрузите данные.")
        else:
            try:
                df_raw = st.session_state["df"].copy()
                leaderboard_df = st.session_state["leaderboard"]
                preds = st.session_state["predictions"]

                with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                    df_raw.to_excel(writer, sheet_name="RawData", index=False)
                    if leaderboard_df is not None:
                        leaderboard_df.to_excel(writer, sheet_name="Leaderboard", index=False)
                    if preds is not None:
                        preds.reset_index().to_excel(writer, sheet_name="Forecast", index=False)

                st.success(f"Результаты сохранены в файл: {save_path}")
            except Exception as e:
                st.error(f"Ошибка при сохранении результатов: {e}")
                logging.error(str(e))

    # 7. Сохранить/загрузить модель
    if st.sidebar.button("Сохранить модель"):
        if st.session_state["predictor"] is None:
            st.warning("Модель ещё не обучена.")
        else:
            predictor = st.session_state["predictor"]
            try:
                save_model(predictor)
                st.success(f"Модель сохранена в папке '{MODEL_PATH}'.")
            except Exception as e:
                st.error(f"Ошибка при сохранении модели: {e}")
                logging.error(str(e))

    if st.sidebar.button("Загрузить модель"):
        try:
            predictor = load_model()
            st.session_state["predictor"] = predictor
            st.success(f"Модель успешно загружена из '{MODEL_PATH}'.")
        except Exception as e:
            st.error(f"Ошибка при загрузке модели: {e}")
            logging.error(str(e))

    # 8. Показ логов
    if st.sidebar.button("Показать логи"):
        logs_content = read_logs()
        st.subheader("Логи обучения")
        st.text(logs_content)


if __name__ == "__main__":
    main()
