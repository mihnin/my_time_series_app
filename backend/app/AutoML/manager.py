import os

import pandas as pd
from sessions.utils import get_session_path
from AutoML.autogluon_strategy import autogluon_strategy

class AutoMLManager:
    strategies = [autogluon_strategy]
    def combine_leaderboards(self, session_id, strategies):
        session_path = get_session_path(session_id)
        dfs = []

        for strategy in strategies:
            file_path = os.path.join(session_path, strategy, "leaderboard.csv")
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df["strategy"] = strategy
                dfs.append(df[["model", "score_val", "strategy"]])
            else:
                print(f"Файл не найден: {file_path}")

        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            combined_df = combined_df.sort_values(by="score_val", ascending=True)
            return combined_df
        else:
            print("Нет данных для объединения")
            return pd.DataFrame(columns=["model", "score_val", "strategy"])
        
    def get_best_strategy(self, session_id):
        session_path = get_session_path(session_id)
        leaderboard_path = os.path.join(session_path, "leaderboard.csv")
        leaderboard = pd.read_csv(leaderboard_path)
        best_strategy = leaderboard.iloc[0]["strategy"]
        if best_strategy == 'autogluon':
            return autogluon_strategy

    def get_strategies(self):
        return self.strategies
        
automl_manager = AutoMLManager()