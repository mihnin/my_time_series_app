# app_training.py
import streamlit as st
import pandas as pd
import shutil
import logging
import time
import gc
import os

from autogluon.timeseries import TimeSeriesPredictor
import psutil

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries, safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from app_saving import save_model_metadata
from src.validation.data_validation import validate_dataset, display_validation_results

def run_training():
    """Функция для запуска обучения модели."""
    df_train = st.session_state.get("df")
    if df_train is None:
        st.warning("Сначала загрузите Train!")
        return False

    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col  = st.session_state.get("id_col_key")

    if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
        st.error("Выберите корректно колонки: дата, target, ID!")
        return False

    try:
        # Валидация данных перед обучением
        with st.spinner("Выполняется валидация данных перед обучением..."):
            validation_results = validate_dataset(df_train, dt_col, tgt_col, id_col)
            
            # Если есть критические ошибки, не продолжаем обучение
            if not validation_results["is_valid"]:
                st.error("Данные не прошли валидацию:")
                for error in validation_results["errors"]:
                    st.error(f"- {error}")
                return False
            
            # Если есть предупреждения, показываем их
            if validation_results["warnings"]:
                with st.expander("Предупреждения о данных", expanded=True):
                    for warning in validation_results["warnings"]:
                        st.warning(f"- {warning}")
        
        # Добавляем индикатор прогресса
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Удаляем старую папку моделей (если есть)
        status_text.text("Подготовка к обучению...")
        shutil.rmtree("AutogluonModels", ignore_errors=True)
        progress_bar.progress(5)

        # Параметры
        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        fill_method_val = st.session_state.get("fill_method_key", "None")
        group_cols_val = st.session_state.get("group_cols_for_fill_key", [])
        use_holidays_val = st.session_state.get("use_holidays_key", False)
        chosen_metric_val = st.session_state.get("metric_key")
        chosen_models_val = st.session_state.get("models_key")
        presets_val = st.session_state.get("presets_key", "high_quality")
        mean_only_val = st.session_state.get("mean_only_key", False)
        p_length = st.session_state.get("prediction_length_key", 3)
        t_limit = st.session_state.get("time_limit_key", None)

        # Приведение дат
        status_text.text("Преобразование дат...")
        df2 = df_train.copy()
        df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")
        progress_bar.progress(10)

        # Добавляем праздники
        if use_holidays_val:
            status_text.text("Добавление признака праздников...")
            df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")
            st.info("Признак `russian_holiday` добавлен.")
        progress_bar.progress(15)

        # Заполняем пропуски
        status_text.text("Заполнение пропусков...")
        df2 = fill_missing_values(df2, fill_method_val, group_cols_val)
        st.session_state["df"] = df2
        progress_bar.progress(20)

        # Статические признаки
        status_text.text("Подготовка статических признаков...")
        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df2[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col: "item_id"}, inplace=True)
            static_df = tmp
            
            # Проверка мультиколлинеарности в статических признаках
            if len(static_feats_val) > 1:
                # Только для числовых признаков
                numeric_static = static_df.select_dtypes(include=['number']).columns.tolist()
                if len(numeric_static) > 1:
                    corr_matrix = static_df[numeric_static].corr()
                    
                    # Находим признаки с высокой корреляцией (>0.7)
                    high_corr_pairs = []
                    for i in range(len(numeric_static)):
                        for j in range(i+1, len(numeric_static)):
                            if abs(corr_matrix.iloc[i, j]) > 0.7:
                                high_corr_pairs.append((numeric_static[i], numeric_static[j], corr_matrix.iloc[i, j]))
                    
                    if high_corr_pairs:
                        st.warning("⚠️ Обнаружена мультиколлинеарность между статическими признаками:")
                        for feat1, feat2, corr in high_corr_pairs:
                            st.warning(f"- {feat1} и {feat2}: корреляция = {corr:.2f}")
                        st.warning("Это может негативно влиять на качество модели.")
        
        progress_bar.progress(25)

        # Преобразуем в TimeSeriesDataFrame
        status_text.text("Преобразование в TimeSeriesDataFrame...")
        try:
            df_ready = safely_prepare_timeseries_data(df2, dt_col, id_col, tgt_col)
            ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
            progress_bar.progress(30)
        except Exception as e:
            st.error(f"Ошибка при преобразовании данных: {e}")
            logging.error(f"Ошибка преобразования данных: {e}")
            return False

        # Частота
        actual_freq = None
        if freq_val != "auto (угадать)":
            status_text.text(f"Преобразование к частоте {freq_val}...")
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
            actual_freq = freq_short
        progress_bar.progress(35)

        # Готовим hyperparameters для выбранных моделей
        status_text.text("Настройка параметров моделей...")
        all_models_opt = "* (все)"
        if not chosen_models_val or (len(chosen_models_val) == 1 and chosen_models_val[0] == all_models_opt):
            hyperparams = None
        else:
            no_star = [m for m in chosen_models_val if m != all_models_opt]
            hyperparams = {m: {} for m in no_star}

            # Если была выбрана модель Chronos, то явно указываем путь, по которому лежит модель
            if "Chronos" in hyperparams:
                hyperparams["Chronos"] = [
                    {"model_path": "autogluon/chronos-bolt-base", "ag_args": {"name_suffix": "ZeroShot"}},
                    {"model_path": "autogluon/chronos-bolt-small", "ag_args": {"name_suffix": "ZeroShot"}},
                    {"model_path": "autogluon/chronos-bolt-small", "fine_tune": True, "ag_args": {"name_suffix": "FineTuned"}}
                ]

        progress_bar.progress(40)

        # Метрика и квантили
        eval_key = chosen_metric_val.split(" ")[0]
        q_levels = [0.5] if mean_only_val else None

        # Параметры кросс-валидации (вместо val_params)
        # Используем параметры, которые доступны напрямую в методе fit()
        num_val_windows = 1
        val_step_size = p_length
        refit_every_n_windows = 1

        # После успешного обучения добавить явное сохранение модели в файл
        model_save_path = "AutogluonModels/TimeSeriesModel"

        # Создаем предиктор
        status_text.text("Создание предиктора...")
        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=p_length,
            eval_metric=eval_key,
            freq=actual_freq,
            quantile_levels=q_levels,
            path=model_save_path,
            verbosity=2
        )
        progress_bar.progress(45)
        
        # Информационное сообщение перед началом обучения
        st.info(f"Начинаем обучение с parametros: preset={presets_val}, time_limit={t_limit}s, prediction_length={p_length}")
        if hyperparams:
            st.info(f"Выбранные модели: {', '.join(hyperparams.keys())}")
        
        start_time = time.time()
        status_text.text("Запуск обучения модели...")
        progress_bar.progress(50)

        try:
            # Создаем дополнительный контейнер для вывода информации во время обучения
            training_info = st.empty()
            
            # Запускаем обучение с правильными параметрами кросс-валидации
            # В AutoGluon 1.2 используем параметры напрямую
            predictor.fit(
                train_data=ts_df,
                time_limit=t_limit,
                presets=presets_val,
                hyperparameters=hyperparams,
                num_val_windows=num_val_windows,
                val_step_size=val_step_size,
                refit_every_n_windows=refit_every_n_windows
            )
            
            # Обновляем прогресс
            elapsed_time = time.time() - start_time
            status_text.text(f"Обучение завершено за {elapsed_time:.2f} секунд!")
            progress_bar.progress(80)
            
        except ValueError as e:
            if "cannot be inferred" in str(e):
                st.error("Не удалось определить частоту автоматически. Укажите freq явно.")
                return False
            else:
                raise
        except Exception as e:
            st.error(f"Ошибка при обучении: {e}")
            logging.error(f"Ошибка при обучении: {e}")
            return False

        # После обучения явно указать, что модель сохранена
        st.success(f"Модель успешно обучена и сохранена в {model_save_path}")
        st.info("Вы можете безопасно взаимодействовать с визуализациями - модель не потеряется")

        # Получаем и отображаем результаты обучения
        status_text.text("Получение результатов обучения...")
        summ = predictor.fit_summary()
        logging.info(f"Fit Summary (raw): {summ}")
        with st.expander("Fit Summary (RAW)"):
            st.write(summ)

        if "weighted_ensemble_info" in st.session_state:
            del st.session_state["weighted_ensemble_info"]

        # Получаем лидерборд
        status_text.text("Формирование лидерборда...")
        lb = predictor.leaderboard(ts_df)
        st.session_state["leaderboard"] = lb
        st.subheader("Лидерборд (Leaderboard)")
        st.dataframe(lb)
        progress_bar.progress(90)

        if not lb.empty:
            best_model = lb.iloc[0]["model"]
            best_score = lb.iloc[0]["score_val"]
            st.session_state["best_model_name"] = best_model
            st.session_state["best_model_score"] = best_score
            st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")

            if best_model == "WeightedEnsemble":
                info_dict = predictor.info()
                ensemble_block = info_dict.get("model_info", {}).get("WeightedEnsemble", {})
                model_weights = ensemble_block.get("model_weights", {})
                logging.info(f"[WeightedEnsemble] Состав и веса: {model_weights}")

                ensemble_info_df = None  # Инициализируем переменную перед условием
                if model_weights:
                    data_rows = [{"Model": model_name, "Weight": w} for model_name, w in model_weights.items()]
                    ensemble_info_df = pd.DataFrame(data_rows)
                else:
                    ensemble_info_df = pd.DataFrame({"Model": ["<нет>"], "Weight": [0.0]})

                st.session_state["weighted_ensemble_info"] = ensemble_info_df
                st.write("### Состав лучшей модели (WeightedEnsemble):")
                st.dataframe(ensemble_info_df)

        # Сохраняем предиктор в session_state
        st.session_state["predictor"] = predictor
        
        # Сохраняем метаданные модели
        status_text.text("Сохранение метаданных модели...")
        save_model_metadata(
            dt_col, tgt_col, id_col,
            static_feats_val, freq_val,
            fill_method_val, group_cols_val,
            use_holidays_val, chosen_metric_val,
            presets_val, chosen_models_val, mean_only_val
        )
        progress_bar.progress(100)
        status_text.text("Обучение успешно завершено!")

        # Освобождаем память
        gc.collect()
        
        # Показываем использование памяти
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
        st.info(f"Текущее использование памяти: {memory_usage:.2f} МБ")

        st.success("Обучение завершено!")
        return True

    except Exception as ex:
        st.error(f"Ошибка обучения: {ex}")
        logging.error(f"Training Exception: {ex}")
        return False
# app_training.py
import streamlit as st
import pandas as pd
import shutil
import logging
import time
import gc
import os

from autogluon.timeseries import TimeSeriesPredictor
import psutil

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries, safely_prepare_timeseries_data
from src.models.forecasting import make_timeseries_dataframe
from app_saving import save_model_metadata
from src.validation.data_validation import validate_dataset, display_validation_results

def run_training():
    """Функция для запуска обучения модели."""
    df_train = st.session_state.get("df")
    if df_train is None:
        st.warning("Сначала загрузите Train!")
        return False

    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col  = st.session_state.get("id_col_key")

    if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
        st.error("Выберите корректно колонки: дата, target, ID!")
        return False

    try:
        # Валидация данных перед обучением
        with st.spinner("Выполняется валидация данных перед обучением..."):
            validation_results = validate_dataset(df_train, dt_col, tgt_col, id_col)
            
            # Если есть критические ошибки, не продолжаем обучение
            if not validation_results["is_valid"]:
                st.error("Данные не прошли валидацию:")
                for error in validation_results["errors"]:
                    st.error(f"- {error}")
                return False
            
            # Если есть предупреждения, показываем их
            if validation_results["warnings"]:
                with st.expander("Предупреждения о данных", expanded=True):
                    for warning in validation_results["warnings"]:
                        st.warning(f"- {warning}")
        
        # Добавляем индикатор прогресса
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Удаляем старую папку моделей (если есть)
        status_text.text("Подготовка к обучению...")
        shutil.rmtree("AutogluonModels", ignore_errors=True)
        progress_bar.progress(5)

        # Параметры
        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        fill_method_val = st.session_state.get("fill_method_key", "None")
        group_cols_val = st.session_state.get("group_cols_for_fill_key", [])
        use_holidays_val = st.session_state.get("use_holidays_key", False)
        chosen_metric_val = st.session_state.get("metric_key")
        chosen_models_val = st.session_state.get("models_key")
        presets_val = st.session_state.get("presets_key", "high_quality")
        mean_only_val = st.session_state.get("mean_only_key", False)
        p_length = st.session_state.get("prediction_length_key", 3)
        t_limit = st.session_state.get("time_limit_key", None)

        # Приведение дат
        status_text.text("Преобразование дат...")
        df2 = df_train.copy()
        df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")
        progress_bar.progress(10)

        # Добавляем праздники
        if use_holidays_val:
            status_text.text("Добавление признака праздников...")
            df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")
            st.info("Признак `russian_holiday` добавлен.")
        progress_bar.progress(15)

        # Заполняем пропуски
        status_text.text("Заполнение пропусков...")
        df2 = fill_missing_values(df2, fill_method_val, group_cols_val)
        st.session_state["df"] = df2
        progress_bar.progress(20)

        # Статические признаки
        status_text.text("Подготовка статических признаков...")
        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df2[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col: "item_id"}, inplace=True)
            static_df = tmp
            
            # Проверка мультиколлинеарности в статических признаках
            if len(static_feats_val) > 1:
                # Только для числовых признаков
                numeric_static = static_df.select_dtypes(include=['number']).columns.tolist()
                if len(numeric_static) > 1:
                    corr_matrix = static_df[numeric_static].corr()
                    
                    # Находим признаки с высокой корреляцией (>0.7)
                    high_corr_pairs = []
                    for i in range(len(numeric_static)):
                        for j in range(i+1, len(numeric_static)):
                            if abs(corr_matrix.iloc[i, j]) > 0.7:
                                high_corr_pairs.append((numeric_static[i], numeric_static[j], corr_matrix.iloc[i, j]))
                    
                    if high_corr_pairs:
                        st.warning("⚠️ Обнаружена мультиколлинеарность между статическими признаками:")
                        for feat1, feat2, corr in high_corr_pairs:
                            st.warning(f"- {feat1} и {feat2}: корреляция = {corr:.2f}")
                        st.warning("Это может негативно влиять на качество модели.")
        
        progress_bar.progress(25)

        # Преобразуем в TimeSeriesDataFrame
        status_text.text("Преобразование в TimeSeriesDataFrame...")
        try:
            df_ready = safely_prepare_timeseries_data(df2, dt_col, id_col, tgt_col)
            ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)
            progress_bar.progress(30)
        except Exception as e:
            st.error(f"Ошибка при преобразовании данных: {e}")
            logging.error(f"Ошибка преобразования данных: {e}")
            return False

        # Частота
        actual_freq = None
        if freq_val != "auto (угадать)":
            status_text.text(f"Преобразование к частоте {freq_val}...")
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
            actual_freq = freq_short
        progress_bar.progress(35)

        # Готовим hyperparameters для выбранных моделей
        status_text.text("Настройка параметров моделей...")
        all_models_opt = "* (все)"
        if not chosen_models_val or (len(chosen_models_val) == 1 and chosen_models_val[0] == all_models_opt):
            hyperparams = None
        else:
            no_star = [m for m in chosen_models_val if m != all_models_opt]
            hyperparams = {m: {} for m in no_star}

            # Если была выбрана модель Chronos, то явно указываем путь, по которому лежит модель
            if "Chronos" in hyperparams:
                hyperparams["Chronos"] = {"model_path": "autogluon/chronos-bolt-base"}

        progress_bar.progress(40)

        # Метрика и квантили
        eval_key = chosen_metric_val.split(" ")[0]
        q_levels = [0.5] if mean_only_val else None

        # Параметры кросс-валидации (вместо val_params)
        # Используем параметры, которые доступны напрямую в методе fit()
        num_val_windows = 1
        val_step_size = p_length
        refit_every_n_windows = 1

        # После успешного обучения добавить явное сохранение модели в файл
        model_save_path = "AutogluonModels/TimeSeriesModel"

        # Создаем предиктор
        status_text.text("Создание предиктора...")
        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=p_length,
            eval_metric=eval_key,
            freq=actual_freq,
            quantile_levels=q_levels,
            path=model_save_path,
            verbosity=2
        )
        progress_bar.progress(45)
        
        # Информационное сообщение перед началом обучения
        st.info(f"Начинаем обучение с parametros: preset={presets_val}, time_limit={t_limit}s, prediction_length={p_length}")
        if hyperparams:
            st.info(f"Выбранные модели: {', '.join(hyperparams.keys())}")
        
        start_time = time.time()
        status_text.text("Запуск обучения модели...")
        progress_bar.progress(50)

        try:
            # Создаем дополнительный контейнер для вывода информации во время обучения
            training_info = st.empty()
            
            # Запускаем обучение с правильными параметрами кросс-валидации
            # В AutoGluon 1.2 используем параметры напрямую
            predictor.fit(
                train_data=ts_df,
                time_limit=t_limit,
                presets=presets_val,
                hyperparameters=hyperparams,
                num_val_windows=num_val_windows,
                val_step_size=val_step_size,
                refit_every_n_windows=refit_every_n_windows
            )
            
            # Обновляем прогресс
            elapsed_time = time.time() - start_time
            status_text.text(f"Обучение завершено за {elapsed_time:.2f} секунд!")
            progress_bar.progress(80)
            
        except ValueError as e:
            if "cannot be inferred" in str(e):
                st.error("Не удалось определить частоту автоматически. Укажите freq явно.")
                return False
            else:
                raise
        except Exception as e:
            st.error(f"Ошибка при обучении: {e}")
            logging.error(f"Ошибка при обучении: {e}")
            return False

        # После обучения явно указать, что модель сохранена
        st.success(f"Модель успешно обучена и сохранена в {model_save_path}")
        st.info("Вы можете безопасно взаимодействовать с визуализациями - модель не потеряется")

        # Получаем и отображаем результаты обучения
        status_text.text("Получение результатов обучения...")
        summ = predictor.fit_summary()
        logging.info(f"Fit Summary (raw): {summ}")
        with st.expander("Fit Summary (RAW)"):
            st.write(summ)

        if "weighted_ensemble_info" in st.session_state:
            del st.session_state["weighted_ensemble_info"]

        # Получаем лидерборд
        status_text.text("Формирование лидерборда...")
        lb = predictor.leaderboard(ts_df)
        st.session_state["leaderboard"] = lb
        st.subheader("Лидерборд (Leaderboard)")
        st.dataframe(lb)
        progress_bar.progress(90)

        if not lb.empty:
            best_model = lb.iloc[0]["model"]
            best_score = lb.iloc[0]["score_val"]
            st.session_state["best_model_name"] = best_model
            st.session_state["best_model_score"] = best_score
            st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")

            if best_model == "WeightedEnsemble":
                info_dict = predictor.info()
                ensemble_block = info_dict.get("model_info", {}).get("WeightedEnsemble", {})
                model_weights = ensemble_block.get("model_weights", {})
                logging.info(f"[WeightedEnsemble] Состав и веса: {model_weights}")

                ensemble_info_df = None  # Инициализируем переменную перед условием
                if model_weights:
                    data_rows = [{"Model": model_name, "Weight": w} for model_name, w in model_weights.items()]
                    ensemble_info_df = pd.DataFrame(data_rows)
                else:
                    ensemble_info_df = pd.DataFrame({"Model": ["<нет>"], "Weight": [0.0]})

                st.session_state["weighted_ensemble_info"] = ensemble_info_df
                st.write("### Состав лучшей модели (WeightedEnsemble):")
                st.dataframe(ensemble_info_df)

        # Сохраняем предиктор в session_state
        st.session_state["predictor"] = predictor
        
        # Сохраняем метаданные модели
        status_text.text("Сохранение метаданных модели...")
        save_model_metadata(
            dt_col, tgt_col, id_col,
            static_feats_val, freq_val,
            fill_method_val, group_cols_val,
            use_holidays_val, chosen_metric_val,
            presets_val, chosen_models_val, mean_only_val
        )
        progress_bar.progress(100)
        status_text.text("Обучение успешно завершено!")

        # Освобождаем память
        gc.collect()
        
        # Показываем использование памяти
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)  # в МБ
        st.info(f"Текущее использование памяти: {memory_usage:.2f} МБ")

        st.success("Обучение завершено!")
        return True

    except Exception as ex:
        st.error(f"Ошибка обучения: {ex}")
        logging.error(f"Training Exception: {ex}")
        return False