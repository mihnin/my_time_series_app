import pandas as pd
import logging

def format_fit_summary(fit_summary):
    """Форматирует fit_summary для более удобочитаемого вывода."""
    if not fit_summary:
        return "Fit Summary отсутствует."

    summary_str = "### Fit Summary:\n\n"
    if 'total_fit_time' in fit_summary:
        summary_str += f"- **Total Fit Time**: {fit_summary['total_fit_time']:.2f} seconds\n"
    if 'best_model' in fit_summary:
        summary_str += f"- **Best Model**: {fit_summary['best_model']}\n"
    if 'best_model_score' in fit_summary:
        summary_str += f"- **Best Model Score**: {fit_summary['best_model_score']:.4f}\n"

    if 'model_fit_summary' in fit_summary and fit_summary['model_fit_summary']:
        summary_str += "\n**Model Fit Details:**\n"
        for model_name, model_info in fit_summary['model_fit_summary'].items():
            summary_str += f"\n**Model: {model_name}**\n"
            if 'fit_time' in model_info:
                summary_str += f"  - Fit Time: {model_info['fit_time']:.2f} seconds\n"
            if 'score' in model_info:
                summary_str += f"  - Score: {model_info['score']:.4f}\n"
            if 'eval_metric' in model_info:
                summary_str += f"  - Eval Metric: {model_info['eval_metric']}\n"
            if 'pred_count' in model_info:
                summary_str += f"  - Predictions Count: {model_info['pred_count']}\n"
            # Добавьте другие детали из model_info, которые важны

    return summary_str

def format_fit_summary_to_df(fit_summary): # New function to format to DataFrame for Excel
    """Преобразует fit_summary в DataFrame для сохранения в Excel."""
    if not fit_summary or not isinstance(fit_summary, dict) or not fit_summary.get('model_fit_summary'): # Robust empty check
        return pd.DataFrame({"Информация": ["Fit Summary отсутствует или не содержит данных о моделях"]}) # More informative message

    data = []
    if 'total_fit_time' in fit_summary:
        data.append({"Метрика": "Total Fit Time", "Значение": f"{fit_summary['total_fit_time']:.2f} seconds"})
    if 'best_model' in fit_summary:
        data.append({"Метрика": "Best Model", "Значение": fit_summary['best_model']})
    if 'best_model_score' in fit_summary:
        data.append({"Метрика": "Best Model Score", "Значение": f"{fit_summary['best_model_score']:.4f}"})

    if 'model_fit_summary' in fit_summary and fit_summary['model_fit_summary']:
        for model_name, model_info in fit_summary['model_fit_summary'].items():
            if isinstance(model_info, dict): # Check if model_info is a dictionary before accessing keys
                data.append({"Метрика": f"Model: {model_name}", "Значение": "---"}) # Separator
                if 'fit_time' in model_info:
                    data.append({"Метрика": f"  Fit Time ({model_name})", "Значение": f"{model_info['fit_time']:.2f} seconds"})
                if 'score' in model_info:
                    data.append({"Метрика": f"  Score ({model_name})", "Значение": f"{model_info['score']:.4f}"})
                if 'eval_metric' in model_info:
                    data.append({"Метрика": f"  Eval Metric ({model_name})", "Значение": model_info['eval_metric']})
                if 'pred_count' in model_info:
                    data.append({"Метрика": f"  Predictions Count ({model_name})", "Значение": model_info['pred_count']})
            else:
                logging.warning(f"Model fit summary for {model_name} is not a dictionary: {model_info}") # Log if model_info is unexpected type

    return pd.DataFrame(data)