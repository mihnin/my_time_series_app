# ======== app.py (обновлённый) ========
import streamlit as st
import logging
import os
import zipfile
import io

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import save_results_to_excel, try_load_existing_model
from src.utils.utils import setup_logger, read_logs, LOG_FILE
from src.help_page import show_help_page


def main():
    # Инициализация логгера
    setup_logger()

    # Расширенное логирование: отметим запуск
    logging.info("========== Приложение запущено ========== ")
    logging.info("=== Запуск приложения Streamlit (main) ===")

    # Пытаемся автоматически загрузить ранее сохранённую модель (если есть)
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try_load_existing_model()

    # Рисуем боковое меню и получаем выбранную страницу
    page_choice = setup_ui()
    logging.info(f"Страница выбрана: {page_choice}")

    # Сформируем сообщение о текущих настройках из session_state
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

    # Подробный лог с текущими параметрами
    logging.info(
        f"Текущие колонки: dt_col={dt_col}, tgt_col={tgt_col}, id_col={id_col}"
    )
    logging.info(
        f"Статические признаки={static_feats}, праздники={use_holidays}, "
        f"метод заполнения пропусков={fill_method_val}, group_cols={group_cols_val}"
    )
    logging.info(
        f"Частота={freq_val}, Метрика={metric_val}, Модели={models_val}, Presets={presets_val}, "
        f"pred_length={prediction_length_val}, time_limit={time_limit_val}, mean_only={mean_only_val}"
    )

    # Блок очистки логов (через ввод “delete”)
    st.sidebar.header("Очистка логов")
    clear_logs_input = st.sidebar.text_input("Введите 'delete', чтобы очистить логи:")
    if st.sidebar.button("Очистить логи"):
        if clear_logs_input.strip().lower() == "delete":
            # 1) Найдём все FileHandler, чтобы закрыть их (иначе файл не удалить на Windows)
            logger = logging.getLogger()
            for handler in logger.handlers[:]:
                if hasattr(handler, 'baseFilename') and os.path.abspath(handler.baseFilename) == os.path.abspath(LOG_FILE):
                    handler.close()
                    logger.removeHandler(handler)

            # 2) Удалим лог-файл
            try:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                    st.warning("Логи очищены!")
                    logging.info("Пользователь очистил логи (файл удалён).")
                else:
                    st.info("Файл логов не найден, нечего очищать.")
            except Exception as e:
                st.error(f"Ошибка при удалении лог-файла: {e}")

            # 3) Пересоздадим пустой лог-файл
            try:
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write("")
                new_file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
                import datetime
                from logging import Formatter
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

    # Если выбрана страница Help — открываем страницу справки
    if page_choice == "Help":
        logging.info("Пользователь на странице Help.")
        show_help_page()
        return

    # ====== Кнопка "Обучить модель" ======
    if st.session_state.get("fit_model_btn"):
        logging.info("Кнопка 'Обучить модель' нажата.")
        train_success = run_training()
        if train_success:
            logging.info("Обучение завершено успешно.")
            if st.session_state.get("train_predict_save_checkbox"):
                logging.info("'Обучение, Прогноз и Сохранение' включено: запускаем прогноз.")
                predict_success = run_prediction()
                if predict_success:
                    logging.info("Прогноз успешно выполнен, сохраняем результаты.")
                    # старый вызов save_results_to_excel можно удалить или оставить — но у нас теперь отдельные кнопки
                    save_path_val = "results.xlsx"  # можно убрать, если не нужно автосохранение
                    _ = save_results_to_excel(save_path_val)
                    st.info("Обучение, прогноз и (авто)сохранение в results.xlsx выполнены успешно!")
        else:
            logging.warning("Обучение завершилось неудачно или было прервано.")

    # ====== Кнопка "Сделать прогноз" ======
    if st.session_state.get("predict_btn"):
        logging.info("Кнопка 'Сделать прогноз' нажата.")
        result = run_prediction()
        if result:
            logging.info("Прогнозирование успешно.")
        else:
            logging.warning("Ошибка при прогнозировании.")

    # =========================== ВАЖНО: новый блок для CSV/Excel ===========================
    #
    # Вместо старого if st.session_state.get("save_btn"):
    # теперь два условия – для CSV и для Excel
    # ======================================================================================
    if st.session_state.get("save_csv_btn"):
        logging.info("Кнопка 'Сохранить результаты в CSV' нажата.")
        # Попробуем выгрузить именно предсказания (predictions).
        preds = st.session_state.get("predictions")
        if preds is None:
            st.warning("Нет данных для сохранения (predictions отсутствуют).")
        else:
            # Конвертируем в CSV в память
            csv_data = preds.reset_index().to_csv(index=False, encoding="utf-8")
            # Предлагаем скачать
            st.download_button(
                label="Скачать CSV файл",
                data=csv_data,
                file_name="results.csv",
                mime="text/csv"
            )
            logging.info("Файл CSV готов к скачиванию.")

    if st.session_state.get("save_excel_btn"):
        logging.info("Кнопка 'Сохранить результаты в Excel' нажата.")
        # Для Excel сделаем логику, схожую с save_results_to_excel, но в память (BytesIO)
        import openpyxl
        import pandas as pd
        from openpyxl.styles import PatternFill
        import io

        df_train = st.session_state.get("df")
        lb = st.session_state.get("leaderboard")
        preds = st.session_state.get("predictions")
        stt_train = st.session_state.get("static_df_train")
        fit_summary_data = st.session_state.get("fit_summary")

        # Проверим, есть ли вообще что сохранять
        has_data_to_save = any([
            df_train is not None,
            lb is not None,
            preds is not None,
            fit_summary_data,
            (stt_train is not None and not stt_train.empty if stt_train is not None else False),
        ])
        if not has_data_to_save:
            st.warning("Нет данных для сохранения в Excel.")
        else:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                # Predictions
                if preds is not None:
                    preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False)

                # Leaderboard
                if lb is not None:
                    lb.to_excel(writer, sheet_name="Leaderboard", index=False)

                # FitSummaryRaw
                if fit_summary_data:
                    fs_sheet = pd.DataFrame([{"Fit_Summary": str(fit_summary_data)}])
                    fs_sheet.to_excel(writer, sheet_name="FitSummaryRaw", index=False)

                # static_df_train (при желании)
                if stt_train is not None and not stt_train.empty:
                    stt_train.to_excel(writer, sheet_name="StaticTrainFeatures", index=False)

                # Подсветка лучшей модели в Leaderboard
                if lb is not None and not lb.empty and "Leaderboard" in writer.sheets:
                    sheet_lb = writer.sheets["Leaderboard"]
                    best_idx = lb.iloc[0].name
                    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    row_excel = best_idx + 2
                    for col_idx in range(1, lb.shape[1] + 1):
                        cell = sheet_lb.cell(row=row_excel, column=col_idx)
                        cell.fill = fill_green

            # Теперь отдаём Excel-файл на скачивание
            st.download_button(
                label="Скачать Excel файл",
                data=excel_buffer.getvalue(),
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            logging.info("Файл Excel готов к скачиванию.")

    # ====== Блок логов приложения (показ и скачивание) ======
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

    # ====== Кнопка “Скачать архив (модели + логи)” ======
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

            # Добавим логи
            log_file_path = LOG_FILE
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
