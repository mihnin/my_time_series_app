from typing import List, Optional, Union
from pydantic import BaseModel, Field


class TrainingParameters(BaseModel):
    datetime_column: str = Field(..., description="Название колонки с датой/временем в загруженном датасете.")
    target_column: str = Field(..., description="Название целевой колонки для прогнозирования.")
    item_id_column: str = Field(..., description="Название колонки с идентификатором временного ряда (item_id).")
    frequency: Optional[str] = Field("auto", description="Частота временного ряда (например, 'D', 'W', 'M', 'auto').")
    fill_missing_method: Optional[str] = Field("None", description="Метод заполнения пропущенных значений (например, 'ffill', 'bfill', 'mean', 'median', 'None').")
    fill_group_columns: Optional[List[str]] = Field([], description="Колонки для группировки при заполнении пропущенных значений.")
    use_russian_holidays: Optional[bool] = Field(False, description="Добавлять ли признаки российских праздников.")
    evaluation_metric: str = Field(..., description="Метрика оценки для AutoGluon (например, 'MASE', 'RMSE', 'sMAPE').")
    models_to_train: Optional[Union[str, List[str], None]] = Field(None, description="Конкретные модели для обучения. Если None или пустой список, обучение не запускается. Если '*', обучаются все доступные модели. Пример: ['DeepAR', 'Chronos'] или '*'.")
    autogluon_preset: Optional[str] = Field("high_quality", description="Пресет AutoGluon (например, 'medium_quality', 'high_quality', 'best_quality').")
    predict_mean_only: Optional[bool] = Field(False, description="Если true, генерируется только средний прогноз (quantile_levels=[0.5]).")
    prediction_length: Optional[int] = Field(3, description="Горизонт прогнозирования.")
    training_time_limit: Optional[int] = Field(None, description="Ограничение времени на обучение в секундах. Если None, то без ограничений.")
    static_feature_columns: Optional[List[str]] = Field([], description="Названия колонок, которые будут использоваться как статические признаки.")
    pycaret_models: Optional[Union[str, List[str], None]] = Field(None, description="Названия моделей для pycaret. Если None или пустой список, обучение не запускается. Если '*', обучаются все доступные модели.")