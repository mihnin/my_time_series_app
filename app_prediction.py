# app_prediction.py
import streamlit as st
import pandas as pd
import plotly.express as px

from src.features.feature_engineering import add_russian_holiday_feature, fill_missing_values
from src.data.data_processing import convert_to_timeseries
from src.models.forecasting import make_timeseries_dataframe, forecast


def run_prediction():
    """Функция для запуска прогнозирования."""
    predictor = st.session_state.get("predictor")
    if predictor is None:
        st.warning("Сначала обучите модель или загрузите уже существующую!")
        return False

    dt_col = st.session_state.get("dt_col_key")
    tgt_col = st.session_state.get("tgt_col_key")
    id_col  = st.session_state.get("id_col_key")

    if dt_col == "<нет>" or tgt_col == "<нет>" or id_col == "<нет>":
        st.error("Проверьте, что выбраны колонки: дата, target, ID!")
        return False

    df_train = st.session_state.get("df")
    if df_train is None:
        st.error("Нет train данных!")
        return False

    try:
        st.subheader("Прогноз на TRAIN")
        df_pred = df_train.copy()

        df_pred[dt_col] = pd.to_datetime(df_pred[dt_col], errors="coerce")

        if st.session_state.get("use_holidays_key", False):
            st.info("Признак `russian_holiday` включён при прогнозировании.")
            df_pred = add_russian_holiday_feature(df_pred, date_col=dt_col, holiday_col="russian_holiday")

        df_pred = fill_missing_values(
            df_pred,
            st.session_state.get("fill_method_key", "None"),
            st.session_state.get("group_cols_for_fill_key", [])
        )

        st.session_state["df"] = df_pred

        static_feats_val = st.session_state.get("static_feats_key", [])
        static_df = None
        if static_feats_val:
            tmp = df_pred[[id_col] + static_feats_val].drop_duplicates(subset=[id_col]).copy()
            tmp.rename(columns={id_col:"item_id"}, inplace=True)
            static_df = tmp

        if tgt_col not in df_pred.columns:
            df_pred[tgt_col] = None

        df_prepared = convert_to_timeseries(df_pred, id_col, dt_col, tgt_col)
        ts_df = make_timeseries_dataframe(df_prepared, static_df=static_df)

        freq_val = st.session_state.get("freq_key", "auto (угадать)")
        if freq_val != "auto (угадать)":
            freq_short = freq_val.split(" ")[0]
            ts_df = ts_df.convert_frequency(freq_short)
            ts_df = ts_df.fill_missing_values(method="ffill")

        preds = forecast(predictor, ts_df)
        st.session_state["predictions"] = preds

        st.subheader("Предсказанные значения (первые строки)")
        st.dataframe(preds.reset_index().head())

        # Повторно выводим лучшую модель
        best_name = st.session_state.get("best_model_name", None)
        best_score = st.session_state.get("best_model_score", None)
        if best_name is not None:
            st.info(f"Лучшая модель при обучении: {best_name}, score_val={best_score:.4f}")

        # Графики
        if "0.5" in preds.columns:
            preds_df = preds.reset_index().rename(columns={"0.5": "prediction"})
            unique_ids = preds_df["item_id"].unique()
            st.subheader("Графики прогноза (0.5) (первые 3)")
            max_graphs = 3
            for i, uid in enumerate(unique_ids[:max_graphs]):
                subset = preds_df[preds_df["item_id"] == uid]
                fig_ = px.line(
                    subset, x="timestamp", y="prediction",
                    title=f"Прогноз для item_id={uid} (0.5)",
                    markers=True
                )
                st.plotly_chart(fig_, use_container_width=True)
        else:
            st.info("Колонка '0.5' не найдена — возможно mean_only=False или квантильные прогнозы отключены.")

        return True

    except Exception as ex:
        st.error(f"Ошибка прогноза: {ex}")
        return False
