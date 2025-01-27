# app.py
import streamlit as st
import logging
import os
import zipfile
import io

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import save_results_to_excel, try_load_existing_model
from src.utils.utils import setup_logger, read_logs
from src.help_page import show_help_page


def main():
    # Инициализация логгера
    setup_logger()

    # Пример детального логирования: отмечаем запуск
    logging.info("========== Приложение запущено ========== ")
    logging.info("=== Запуск приложения Streamlit (main) ===")

    # Если нет модели в session_state, пытаемся загрузить старую
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try_load_existing_model()

    # Отрисовываем боковую панель и получаем выбранную страницу
    page_choice = setup_ui()
    logging.info(f"Выбрана страница: {page_choice}")

    # Сформируем сообщение о текущих параметрах из session_state
    # (при этом проверяем, что ключи существуют, иначе 'Unknown')
    dt_col = st.session_state.get("dt_col_key", "<нет>")
    tgt_col = st.session_state.get("tgt_col_key", "<нет>")
    id_col  = st.session_state.get("id_col_key", "<нет>")

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

    # Пишем подробный лог
    logging.info(
        f"Пользователь задал dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}, "
        f"static_feats={static_feats}, use_holidays={use_holidays}"
    )
    logging.info(
        f"Метод заполнения пропусков: {fill_method_val}, group_cols_for_fill={group_cols_val}"
    )
    logging.info(f"Выбрана частота: {freq_val}")
    logging.info(
        f"Метрика: {metric_val}, модели: {models_val}, presets: {presets_val}, "
        f"prediction_length={prediction_length_val}, time_limit={time_limit_val}, mean_only={mean_only_val}"
    )

    if page_choice == "Help":
        show_help_page()
        return

    # ====== Кнопки: "Обучить модель", "Сделать прогноз", "Сохранить результаты" ======
    if st.session_state.get("fit_model_btn"):
        train_success = run_training()
        if train_success and st.session_state.get("train_predict_save_checkbox"):
            predict_success = run_prediction()
            if predict_success:
                save_path_val = st.session_state.get("save_path_key", "results.xlsx")
                save_result = save_results_to_excel(save_path_val)
                if save_result:
                    st.info("Обучение, прогноз и сохранение результатов выполнены успешно!")

    if st.session_state.get("predict_btn"):
        run_prediction()

    if st.session_state.get("save_btn"):
        save_path_val = st.session_state.get("save_path_key", "results.xlsx")
        save_result = save_results_to_excel(save_path_val)

    # ====== Кнопки логи приложения, скачать логи, скачать архив моделей ======
    if st.session_state.get("show_logs_btn"):
        logs_text = read_logs()
        st.subheader("Логи приложения")
        st.text_area("logs", logs_text, height=300)

    if st.session_state.get("download_logs_btn"):
        logs_text = read_logs()
        st.download_button(
            label="Скачать лог-файл",
            data=logs_text,
            file_name="app.log",
            mime="text/plain",
        )

    if st.session_state.get("download_model_and_logs"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            model_dir = "AutogluonModels"
            if os.path.exists(model_dir):
                for root, dirs, files in os.walk(model_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=model_dir)
                        zf.write(full_path, arcname=os.path.join("AutogluonModels", rel_path))

            log_file_path = "logs/app.log"
            if os.path.exists(log_file_path):
                zf.write(log_file_path, arcname="logs/app.log")

        st.download_button(
            label="Скачать архив (модели + логи)",
            data=zip_buffer.getvalue(),
            file_name="model_and_logs.zip",
            mime="application/zip"
        )


if __name__ == "__main__":
    main()
