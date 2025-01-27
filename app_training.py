# app_training.py
import streamlit as st
import pandas as pd
import shutil
import logging

from autogluon.timeseries import TimeSeriesPredictor

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe
from app_saving import MODEL_DIR, save_model_metadata, format_fit_summary


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
        shutil.rmtree("AutogluonModels", ignore_errors=True)

        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        fill_method_val = st.session_state.get("fill_method_key","None")
        group_cols_val = st.session_state.get("group_cols_for_fill_key",[])
        use_holidays_val = st.session_state.get("use_holidays_key", False)
        chosen_metric_val = st.session_state.get("metric_key")
        chosen_models_val = st.session_state.get("models_key")
        presets_val = st.session_state.get("presets_key", "medium_quality")
        mean_only_val = st.session_state.get("mean_only_key", False)
        p_length = st.session_state.get("prediction_length_key", 10)
        t_limit = st.session_state.get("time_limit_key", 60)

        df2 = df_train.copy()
        df2[dt_col] = pd.to_datetime(df2[dt_col], errors="coerce")

        if use_holidays_val:
            st.info("Признак `russian_holiday` добавлен и будет учитываться при обучении модели.")
            df2 = add_russian_holiday_feature(df2, date_col=dt_col, holiday_col="russian_holiday")

        df2 = fill_missing_values(df2, fill_method_val, group_cols_val)
        st.session_state["df"] = df2

        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df2[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col:"item_id"}, inplace=True)
            static_df = tmp

        df_ready = convert_to_timeseries(df2, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_ready, static_df=static_df)

        actual_freq = None
        if freq_val != "auto (угадать)":
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")
            actual_freq = freq_short

        hyperparams = None
        all_models_opt = "* (все)"
        if (len(chosen_models_val) == 1 and chosen_models_val[0] == all_models_opt) or len(chosen_models_val) == 0:
            hyperparams = None
        else:
            no_star = [m for m in chosen_models_val if m != all_models_opt]
            hyperparams = {m:{} for m in no_star}

        eval_key = chosen_metric_val.split(" ")[0]
        q_levels = [0.5] if mean_only_val else None

        predictor = TimeSeriesPredictor(
            target="target",
            prediction_length=p_length,
            eval_metric=eval_key,
            freq=actual_freq,
            quantile_levels=q_levels,
            path=MODEL_DIR
        )

        st.info("Начинаем обучение...")
        try:
            predictor.fit(
                train_data=ts_df,
                time_limit=t_limit,
                presets=presets_val,
                hyperparameters=hyperparams
            )
        except ValueError as e:
            if "cannot be inferred" in str(e):
                st.error("Не удалось определить частоту автоматически. Укажите частоту явно (freq).")
                return False
            else:
                raise

        summ = predictor.fit_summary()
        st.session_state["fit_summary"] = summ

        logging.info(f"Fit Summary (raw): {summ}")

        # Для отладки можно вывести RAW fit summary
        with st.expander("Fit Summary (RAW)"):
            st.write(summ)

        # Удаляем/закомментируем:
# if summ:
#     detailed_fit_summary_str = format_fit_summary(summ)
#     with st.expander("Fit Summary (Подробно)"):
#         st.markdown(detailed_fit_summary_str)
# else:
#     st.warning("Fit Summary is empty.")
#     with st.expander("Fit Summary (Подробно)"):
#         st.text("Fit Summary is not available.")

        st.session_state["predictor"] = predictor
        st.success("Модель успешно обучена!")

        lb = predictor.leaderboard(ts_df)
        st.session_state["leaderboard"] = lb
        st.subheader("Лидерборд (Leaderboard)")
        st.dataframe(lb)

        if not lb.empty:
            best_model = lb.iloc[0]["model"]
            best_score = lb.iloc[0]["score_val"]
            st.session_state["best_model_name"] = best_model
            st.session_state["best_model_score"] = best_score
            st.info(f"Лучшая модель: {best_model}, score_val={best_score:.4f}")

        # Сохраняем настройки в JSON
        save_model_metadata(
            dt_col, tgt_col, id_col,
            static_feats_val, freq_val,
            fill_method_val, group_cols_val,
            use_holidays_val, chosen_metric_val,
            presets_val, chosen_models_val, mean_only_val
        )

        return True

    except Exception as ex:
        st.error(f"Ошибка обучения: {ex}")
        logging.error(f"Training Exception: {ex}")
        return False
