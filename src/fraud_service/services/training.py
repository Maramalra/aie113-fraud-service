"""Use case: train a model from the payments data, choose the threshold, measure it, save it.

Same steps and numbers as the notebook. Data tables (pandas) are used here because this job is
about bulk data; the scikit-learn specifics stay in the adapter.
"""
from collections.abc import Callable
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from fraud_service.config import Settings
from fraud_service.domain.decision import choose_threshold
from fraud_service.domain.payment import FEATURE_NAMES

FEATURES = list(FEATURE_NAMES)


def build_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by time and add the hour of the day, as in the notebook."""
    df = df.sort_values("Time", kind="stable").reset_index(drop=True)
    df["hour"] = (df["Time"] // 3600) % 24
    return df


def split_by_time(df: pd.DataFrame, train_share: float, valid_share: float):
    n = len(df)
    train_end = int(n * train_share)
    valid_end = int(n * (train_share + valid_share))
    return df.iloc[:train_end], df.iloc[train_end:valid_end], df.iloc[valid_end:]


def precision_at(scores: np.ndarray, y: np.ndarray, threshold: float) -> float | None:
    alert = scores >= threshold
    return float((alert & (y == 1)).sum() / alert.sum()) if alert.sum() else None


def train(df: pd.DataFrame, settings: Settings, fit: Callable, score: Callable, average_precision: Callable):
    """Returns (model, info). `fit`, `score` and `average_precision` come from the model adapter."""
    df = build_inputs(df)
    train_df, valid_df, test_df = split_by_time(df, settings.train_share, settings.valid_share)

    model = fit(train_df[FEATURES], train_df["Class"], settings.random_seed)

    valid_scores = score(model, valid_df[FEATURES])
    y_valid = valid_df["Class"].to_numpy()
    threshold = choose_threshold(
        {t: precision_at(valid_scores, y_valid, t) for t in settings.thresholds_to_try}, settings.min_precision
    )

    test_scores = score(model, test_df[FEATURES])
    y_true = test_df["Class"].to_numpy()
    alert = test_scores >= threshold
    caught = int((alert & (y_true == 1)).sum())
    rule_alert = test_df["Amount"].to_numpy() > settings.amount_rule
    rule_caught = int((rule_alert & (y_true == 1)).sum())
    typical = train_df.loc[train_df["Class"] == 0, FEATURES].median()

    import sklearn  # only for recording the version the model was trained with

    info = {
        "model_version": settings.model_version,
        "model_type": type(model).__name__,
        "trained_on": datetime.now(UTC).strftime("%Y-%m-%d"),
        "scikit_learn_version": sklearn.__version__,
        "features": FEATURES,
        "threshold": threshold,
        "threshold_rule": f"lowest tried threshold where at least {settings.min_precision:.0%} "
                          "of validation alerts are real fraud",
        "typical_values": {name: float(v) for name, v in typical.items()},
        "data": {
            "source": settings.data_url,
            "rows": int(len(df)),
            "frauds": int(df["Class"].sum()),
            "train_rows": int(len(train_df)),
            "valid_rows": int(len(valid_df)),
            "test_rows": int(len(test_df)),
            "test_frauds": int(y_true.sum()),
        },
        "test_metrics": {
            "alerts": int(alert.sum()),
            "frauds_caught": caught,
            "precision": caught / int(alert.sum()) if alert.sum() else None,
            "recall": caught / int(y_true.sum()),
            "false_alarms": int((alert & (y_true == 0)).sum()),
            "missed_frauds": int((~alert & (y_true == 1)).sum()),
            "average_precision": float(average_precision(y_true, test_scores)),
            "accuracy": float((alert == (y_true == 1)).mean()),
        },
        "baselines_on_test": {
            "always_not_fraud_accuracy": float((y_true == 0).mean()),
            "amount_rule_recall": rule_caught / int(y_true.sum()),
            "amount_rule_precision": rule_caught / int(rule_alert.sum()) if rule_alert.sum() else None,
        },
    }
    return model, info
