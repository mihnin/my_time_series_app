# ======== app.py (обновлённый) ========
import streamlit as st
import logging
import os
import zipfile
import io

from app_ui import setup_ui
from app_training import run_training
from app_prediction import run_prediction
from app_saving import try_load_existing_model, save_model_metadata, load_model_metadata
from src.utils.utils import setup_logger, read_logs, LOG_FILE
from src.help_page import show_help_page

import pandas as pd
from openpyxl.styles import PatternFill


def main():
    # Инициализируем логгер
    setup_logger()
    logging.info("========== Приложение запущено ========== ")
    logging.info("=== Запуск приложения Streamlit (main) ===")

    # Пытаемся автоматически загрузить ранее сохранённую модель (если есть)
    if "predictor" not in st.session_state or st.session_state["predictor"] is None:
        try_load_existing_model()

    # Рисуем боковое меню/страницы
    page_choice = setup_ui()
    logging.info(f"Страница выбрана: {page_choice}")

    # Логируем текущие настройки
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

    # ------------------- Очистка логов -------------------
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

    # Если выбрана страница Help
    if page_choice == "Help":
        logging.info("Пользователь на странице Help.")
        show_help_page()
        return

    # -------------- Кнопка «Обучить модель» --------------
    if st.session_state.get("fit_model_btn"):
        logging.info("Кнопка 'Обучить модель' нажата.")
        train_success = run_training()
        if train_success:
            logging.info("Обучение завершено успешно.")
            # Сохраним метаданные в model_info.json (если нужно)
            save_model_metadata(
                dt_col, tgt_col, id_col,
                static_feats, freq_val,
                fill_method_val, group_cols_val,
                use_holidays, metric_val,
                presets_val, models_val, mean_only_val
            )

            # Если установлен чекбокс «Обучение, Прогноз и Сохранение»
            if st.session_state.get("train_predict_save_checkbox"):
                logging.info("'Обучение, Прогноз и Сохранение' включено.")
                predict_success = run_prediction()
                if predict_success:
                    logging.info("Прогноз успешно выполнен.")
                    st.info("Обучение и прогноз завершены, теперь формируем Excel для скачивания...")

                    # Автоматически формируем Excel в памяти
                    excel_buffer = io.BytesIO()
                    df_train = st.session_state.get("df")
                    lb = st.session_state.get("leaderboard")
                    preds = st.session_state.get("predictions")
                    stt_train = st.session_state.get("static_df_train")
                    ensemble_info_df = st.session_state.get("weighted_ensemble_info")  # инфа об ансамбле

                    # Проверяем, есть ли данные
                    has_data_to_save = any([
                        df_train is not None,
                        lb is not None,
                        preds is not None,
                        (stt_train is not None and not stt_train.empty if stt_train is not None else False),
                        (ensemble_info_df is not None),
                    ])
                    if has_data_to_save:
                        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                            # Predictions
                            if preds is not None:
                                preds.reset_index().to_excel(writer, sheet_name="Predictions", index=False)

                            # Leaderboard
                            if lb is not None:
                                lb.to_excel(writer, sheet_name="Leaderboard", index=False)
                                # Подсветим лучшую модель (зелёный фон)
                                sheet_lb = writer.sheets["Leaderboard"]
                                best_idx = lb.iloc[0].name
                                fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                                row_excel = best_idx + 2
                                for col_idx in range(1, lb.shape[1] + 1):
                                    cell = sheet_lb.cell(row=row_excel, column=col_idx)
                                    cell.fill = fill_green

                            # static_df_train
                            if stt_train is not None and not stt_train.empty:
                                stt_train.to_excel(writer, sheet_name="StaticTrainFeatures", index=False)

                            # Создаём вкладку WeightedEnsembleInfo (если есть данные)
                            if ensemble_info_df is not None and not ensemble_info_df.empty:
                                ensemble_info_df.to_excel(writer, sheet_name="WeightedEnsembleInfo", index=False)

                        # Выводим кнопку скачивания
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

    # -------------- Кнопка «Сделать прогноз» --------------
    if st.session_state.get("predict_btn"):
        logging.info("Кнопка 'Сделать прогноз' нажата.")
        result = run_prediction()
        if result:
            logging.info("Прогноз успешно.")
        else:
            logging.warning("Ошибка при прогнозировании.")

    # -------- Новые кнопки «Сохранить в CSV/Excel» (В ПАМЯТИ) --------
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

    if st.session_state.get("save_excel_btn"):
        logging.info("Кнопка 'Сохранить результаты в Excel' нажата.")
        df_train = st.session_state.get("df")
        lb = st.session_state.get("leaderboard")
        preds = st.session_state.get("predictions")
        stt_train = st.session_state.get("static_df_train")
        ensemble_info_df = st.session_state.get("weighted_ensemble_info")  # инфа об ансамбле

        has_data_to_save = any([
            df_train is not None,
            lb is not None,
            preds is not None,
            (stt_train is not None and not stt_train.empty if stt_train is not None else False),
            (ensemble_info_df is not None),
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
                    # Подсветим лучшую модель
                    sheet_lb = writer.sheets["Leaderboard"]
                    best_idx = lb.iloc[0].name
                    fill_green = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    row_excel = best_idx + 2
                    for col_idx in range(1, lb.shape[1] + 1):
                        cell = sheet_lb.cell(row=row_excel, column=col_idx)
                        cell.fill = fill_green

                # static_df_train
                if stt_train is not None and not stt_train.empty:
                    stt_train.to_excel(writer, sheet_name="StaticTrainFeatures", index=False)

                # Создаём вкладку WeightedEnsembleInfo (если есть данные)
                if ensemble_info_df is not None and not ensemble_info_df.empty:
                    ensemble_info_df.to_excel(writer, sheet_name="WeightedEnsembleInfo", index=False)

            st.download_button(
                label="Скачать Excel файл",
                data=excel_buffer.getvalue(),
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            logging.info("Файл Excel готов к скачиванию (ручной).")

    # ------------------- Логи и скачивание логов -------------------
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

    # ------------------- Скачивание архива (модели+логи) -------------------
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

            # Добавляем логи
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
