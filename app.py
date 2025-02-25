# app.py
# app.py
import streamlit as st
import logging
import os
import zipfile
import io
import pandas as pd
import psutil
from openpyxl.styles import PatternFill

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import try_load_existing_model, save_model_metadata, load_model_metadata
from src.utils.utils import setup_logger, read_logs, LOG_FILE
from src.help_page import show_help_page
from src.utils.exporter import generate_excel_buffer
from data_analysis import run_data_analysis  # Новый импорт

def main():
    # Инициализация логгера
    setup_logger()
    logging.info("========== Приложение запущено ========== ")
    logging.info("=== Запуск приложения Streamlit (main) ===")
    
    # В начале функции, добавьте:
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try:
            from autogluon.timeseries import TimeSeriesPredictor
            model_path = "AutogluonModels/TimeSeriesModel"
            if os.path.exists(model_path):
                st.session_state["predictor"] = TimeSeriesPredictor.load(model_path)
                st.success("Загружена ранее обученная модель")
        except Exception as e:
            logging.error(f"Не удалось загрузить сохраненную модель: {e}")
    
    # После загрузки предиктора
    if "predictor" in st.session_state and st.session_state["predictor"] is not None:
        # Если предсказания уже были сделаны, но приложение было перезагружено
        if "predictions" in st.session_state and "graphs_data" not in st.session_state:
            # Инициализируем данные для графиков
            preds = st.session_state["predictions"]
            if preds is not None and "0.5" in preds.columns:
                preds_df = preds.reset_index().rename(columns={"0.5": "prediction"})
                unique_ids = preds_df["item_id"].unique()
                
                if "graphs_data" not in st.session_state:
                    st.session_state["graphs_data"] = {}
                
                st.session_state["graphs_data"]["preds_df"] = preds_df
                st.session_state["graphs_data"]["unique_ids"] = unique_ids
    
    # Рисуем боковое меню и получаем выбранную страницу
    page_choice = setup_ui()
    logging.info(f"Страница выбрана: {page_choice}")
    
    # Лог текущих настроек
    dt_col = st.session_state.get("dt_col_key", "<нет>")
    tgt_col = st.session_state.get("tgt_col_key", "<нет>")
    id_col = st.session_state.get("id_col_key", "<нет>")
    
    static_feats = st.session_state.get("static_feats_key", [])
    use_holidays = st.session_state.get("use_holidays_key", False)
    fill_method_val = st.session_state.get("fill_method_key", "None")
    group_cols_val = st.session_state.get("group_cols_for_fill_key", [])
    freq_val = st.session_state.get("freq_key", "auto (угадать)")
    
    metric_val = st.session_state.get("metric_key", "MASE (Mean absolute scaled error)")
    models_val = st.session_state.get("models_key", ["* (все)"])
    presets_val = st.session_state.get("presets_key", "medium_quality")
    prediction_length_val = st.session_state.get("prediction_length_key", 10)
    time_limit_val = st.session_state.get("time_limit_key", 60)
    mean_only_val = st.session_state.get("mean_only_key", False)
    
    logging.info(
        f"Текущие колонки: dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}"
    )
    logging.info(
        f"Статические признаки={static_feats}, праздники={use_holidays}, "
        f"метод заполнения={fill_method_val}, group_cols={group_cols_val}"
    )
    logging.info(
        f"freq={freq_val}, metric={metric_val}, models={models_val}, presets={presets_val}, "
        f"pred_len={prediction_length_val}, time_limit={time_limit_val}, mean_only={mean_only_val}"
    )
    
    # Отображение информации о памяти
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
    st.sidebar.markdown(f"**Использование памяти**: {memory_usage:.2f} МБ")
    
    # ------------- Очистка логов -------------
    st.sidebar.header("Очистка логов")
    clear_logs_input = st.sidebar.text_input("Введите 'delete', чтобы очистить логи:")
    if st.sidebar.button("Очистить логи"):
        if clear_logs_input.strip().lower() == "delete":
            logger = logging.getLogger()
            for handler in logger.handlers[:]:
                if hasattr(handler, 'baseFilename') and os.path.abspath(handler.baseFilename) == os.path.abspath(LOG_FILE):
                    handler.close()
                    logger.removeHandler(handler)
            try:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                    st.warning("Логи очищены!")
                    logging.info("Пользователь очистил логи (файл удалён).")
                else:
                    st.info("Файл логов не найден, нечего очищать.")
            except Exception as e:
                st.error(f"Ошибка при удалении лог-файла: {e}")
            # Пересоздаём пустой лог-файл
            try:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write("")
                from logging import Formatter
                new_file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
                formatter = Formatter(
                    "%(asctime)s [%(levelname)s] %(module)s.%(funcName)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                new_file_handler.setFormatter(formatter)
                logger.addHandler(new_file_handler)
                logger.info("Создан новый log-файл после очистки.")
            except Exception as e:
                st.error(f"Ошибка при создании нового лог-файла: {e}")
        else:
            st.warning("Неверное слово. Логи не очищены.")
    
    # Управление памятью
    if st.sidebar.button("Очистить память"):
        # Освобождаем неиспользуемые объекты
        for key in list(st.session_state.keys()):
            if key not in ["df", "predictor", "page_choice", "dt_col_key", "tgt_col_key", "id_col_key", 
                          "static_feats_key", "use_holidays_key", "fill_method_key", "group_cols_for_fill_key",
                          "freq_key", "metric_key", "models_key", "presets_key", "prediction_length_key",
                          "time_limit_key", "mean_only_key"]:
                del st.session_state[key]
        
        import gc
        gc.collect()
        
        # Обновляем информацию о памяти
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
        st.sidebar.success(f"Память очищена. Текущее использование: {memory_usage:.2f} МБ")
    
    # Если выбрана страница Help — показываем справку и выходим
    if page_choice == "Help":
        logging.info("Пользователь на странице Help.")
        show_help_page()
        return
    
    # Если выбрана страница анализа данных - запускаем анализ и выходим
    # Если выбрана страница анализа данных - запускаем анализ и выходим
    if page_choice == "Анализ данных":
        logging.info("Пользователь на странице анализа данных.")
        try:
            run_data_analysis()
        except Exception as e:
            st.error(f"Произошла ошибка при анализе данных: {e}")
            logging.error(f"Ошибка в run_data_analysis: {e}")
        return
    
    # ------------- Обучение модели -------------
    if st.session_state.get("fit_model_btn"):
        logging.info("Кнопка 'Обучить модель' нажата.")
        train_success = run_training()
        if train_success:
            logging.info("Обучение завершено успешно.")
            # Сохраняем метаданные модели
            save_model_metadata(
                dt_col, tgt_col, id_col,
                static_feats, freq_val,
                fill_method_val, group_cols_val,
                use_holidays, metric_val,
                presets_val, models_val, mean_only_val
            )
            # Если выбран режим "Обучение, Прогноз и Сохранение"
            if st.session_state.get("train_predict_save_checkbox"):
                logging.info("'Обучение, Прогноз и Сохранение' включено.")
                predict_success = run_prediction()
                if predict_success:
                    logging.info("Прогноз успешно выполнен.")
                    st.info("Обучение и прогноз завершены, теперь формируем Excel для скачивания...")
                    # Получаем данные для экспорта
                    df_train = st.session_state.get("df")
                    lb = st.session_state.get("leaderboard")
                    preds = st.session_state.get("predictions")
                    stt_train = st.session_state.get("static_df_train")
                    ensemble_info_df = st.session_state.get("weighted_ensemble_info")
                    
                    has_data_to_save = any([
                        df_train is not None,
                        lb is not None,
                        preds is not None,
                        (stt_train is not None and not stt_train.empty),
                        (ensemble_info_df is not None)
                    ])
                    if has_data_to_save:
                        excel_buffer = generate_excel_buffer(preds, lb, stt_train, ensemble_info_df)
                        st.download_button(
                            label="Скачать Excel (авто)",
                            data=excel_buffer.getvalue(),
                            file_name="results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        st.success("Файл Excel готов к скачиванию!")
                    else:
                        st.warning("Нет данных для сохранения (после обучения/прогноза).")
                else:
                    logging.warning("Ошибка при прогнозировании.")
    
    # ------------- Прогноз -------------
    if st.session_state.get("predict_btn"):
        logging.info("Кнопка 'Сделать прогноз' нажата.")
        
        # Добавляем эту проверку перед вызовом run_prediction:
        if "graphs_data" in st.session_state:
            # Очищаем старые данные графиков перед новым прогнозом
            del st.session_state["graphs_data"]
        
        result = run_prediction()
        if result:
            logging.info("Прогноз успешно выполнен.")
        else:
            logging.warning("Ошибка при прогнозировании.")
    
    # ------------- Сохранение результатов в CSV -------------
    if st.session_state.get("save_csv_btn"):
        logging.info("Кнопка 'Сохранить результаты в CSV' нажата.")
        preds = st.session_state.get("predictions")
        if preds is None:
            st.warning("Нет данных для сохранения (predictions отсутствуют).")
        else:
            csv_data = preds.reset_index().to_csv(index=False, encoding="utf-8")
            st.download_button(
                label="Скачать CSV файл",
                data=csv_data,
                file_name="results.csv",
                mime="text/csv"
            )
            logging.info("Файл CSV с предиктом сформирован и готов к скачиванию.")
    
    # ------------- Сохранение результатов в Excel -------------
    if st.session_state.get("save_excel_btn"):
        logging.info("Кнопка 'Сохранить результаты в Excel' нажата.")
        preds = st.session_state.get("predictions")
        lb = st.session_state.get("leaderboard")
        stt_train = st.session_state.get("static_df_train")
        ensemble_info_df = st.session_state.get("weighted_ensemble_info")
        
        has_data_to_save = preds is not None
        if not has_data_to_save:
            st.warning("Нет данных прогноза для сохранения в Excel.")
        else:
            excel_buffer = generate_excel_buffer(preds, lb, stt_train, ensemble_info_df)
            st.download_button(
                label="Скачать Excel файл",
                data=excel_buffer.getvalue(),
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            logging.info("Файл Excel готов к скачиванию (ручной).")
    
    # ------------- Логи приложения -------------
    if st.session_state.get("show_logs_btn"):
        logging.info("Кнопка 'Показать логи' нажата.")
        logs_text = read_logs()
        st.subheader("Логи приложения")
        st.text_area("logs", logs_text, height=300)
    
    if st.session_state.get("download_logs_btn"):
        logging.info("Кнопка 'Скачать логи' нажата.")
        logs_text = read_logs()
        st.download_button(
            label="Скачать лог-файл",
            data=logs_text,
            file_name="app.log",
            mime="text/plain",
        )
    
    # ------------- Выгрузка моделей и логов (архив) -------------
    if st.session_state.get("download_model_and_logs"):
        logging.info("Кнопка 'Скачать архив (модели + логи)' нажата.")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            model_dir = "AutogluonModels"
            if os.path.exists(model_dir):
                for root, dirs, files in os.walk(model_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=model_dir)
                        zf.write(full_path, arcname=os.path.join("AutogluonModels", rel_path))
            if os.path.exists(LOG_FILE):
                zf.write(LOG_FILE, arcname="logs/app.log")
        st.download_button(
            label="Скачать архив (модели + логи)",
            data=zip_buffer.getvalue(),
            file_name="model_and_logs.zip",
            mime="application/zip"
        )

if __name__ == "__main__":
    main()

