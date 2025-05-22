from abc import ABC, abstractmethod
import os
from typing import Any, Dict, Optional

import pandas as pd

from sessions.utils import get_session_path
from training.model import TrainingParameters

class AutoMLStrategy(ABC):
    """Abstract base class for AutoML strategies."""

    @abstractmethod
    def train(
        self,
        ts_df: Any, # Prepared TimeSeriesDataFrame (AutoGluon) or pd.DataFrame (PyCaret)
        training_params: TrainingParameters,
        session_id: str, # For logging/status updates
    ) -> Dict[str, Any]: # Returns metadata like leaderboard path, best score for this strategy
        """Trains the model using the specific AutoML library."""
        pass

    @abstractmethod
    def predict(
        self,
        ts_df,
        session_id: str,
        training_params: TrainingParameters
    ) -> pd.DataFrame: # Returns predictions
        """Makes predictions using a trained model."""
        pass


