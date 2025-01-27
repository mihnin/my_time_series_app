# app.py
import streamlit as st
import os
import io
import zipfile
import shutil

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import save_results_to_excel, try_load_existing_model
from src.utils.utils import setup_logger, read_logs
from src.help_page import show_help_page

def main():
    # Настраиваем логгер
    setup_logger()

    # Пробуем автоматически загрузить уже обученную модель, если есть
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try_load_existing_model()

    # Рисуем боковую панель и основные элементы интерфейса
    page_choice = setup_ui()

    # Если нажат "Help"
    if page_choice == "Help":
        show_help_page()
        return

    # Обучение + (по желанию) Прогноз + Сохранение
    if st.session_state.get("fit_model_btn"):
        train_success = run_training()
        if train_success and st.session_state.get("train_predict_save_checkbox"):
            predict_success = run_prediction()
            if predict_success:
                save_path_val = st.session_state.get("save_path_key", "results.xlsx")
                save_result = save_results_to_excel(save_path_val)
                if save_result:
                    st.info("Обучение, прогноз и сохранение результатов выполнены успешно!")

    # Прогноз отдельно
    if st.session_state.get("predict_btn"):
        run_prediction()

    # Сохранение результатов отдельно
    if st.session_state.get("save_btn"):
        save_path_val = st.session_state.get("save_path_key", "results.xlsx")
        save_result = save_results_to_excel(save_path_val)

    # ====== ЛОГИ ======
    # Показать логи
    if st.session_state.get("show_logs_btn"):
        logs_text = read_logs()
        st.subheader("Логи приложения")
        st.text_area("logs", logs_text, height=300)

    # Скачать логи
    if st.session_state.get("download_logs_btn"):
        logs_text = read_logs()
        st.download_button(
            label="Скачать лог-файл",
            data=logs_text,
            file_name="app.log",
            mime="text/plain",
        )

    # Скачать всё содержимое AutogluonModels + логи
    if st.session_state.get("download_model_and_logs"):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            # Добавляем папку AutogluonModels
            model_dir = "AutogluonModels"
            if os.path.exists(model_dir):
                for root, dirs, files in os.walk(model_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=model_dir)
                        zf.write(full_path, arcname=os.path.join("AutogluonModels", rel_path))
            # Добавляем логи, если есть
            log_file_path = "logs/app.log"
            if os.path.exists(log_file_path):
                zf.write(log_file_path, arcname="logs/app.log")

        st.download_button(
            label="Скачать архив моделей и логов",
            data=zip_buffer.getvalue(),
            file_name="model_and_logs.zip",
            mime="application/zip"
        )

if __name__ == "__main__":
    main()
