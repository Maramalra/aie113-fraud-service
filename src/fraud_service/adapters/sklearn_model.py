"""Adapter: everything that knows about scikit-learn and joblib lives here."""
import json
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score


class SklearnFraudModel:
    """A trained model plus its facts (model_info.json). Implements the domain's FraudModel port."""

    def __init__(self, estimator, info: dict) -> None:
        self._estimator = estimator
        self.info = info
        self.version: str = info["model_version"]
        self.feature_names: list[str] = list(info["features"])
        self.typical_values: dict[str, float] = dict(info["typical_values"])
        self.review_threshold: float = float(info["threshold"])

    @classmethod
    def load(cls, model_path: Path, info_path: Path) -> "SklearnFraudModel":
        return cls(joblib.load(model_path), json.loads(Path(info_path).read_text()))

    def score_many(self, rows: Sequence[dict[str, float]]) -> list[float]:
        frame = pd.DataFrame(list(rows), columns=self.feature_names)
        return [float(s) for s in self._estimator.predict_proba(frame)[:, 1]]


# --- training helpers, handed to services.training.train -------------------------------------
def fit(X: pd.DataFrame, y: pd.Series, seed: int) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(  # same settings as the notebook
        learning_rate=0.05, max_iter=300, max_leaf_nodes=15, l2_regularization=1.0,
        early_stopping=False, random_state=seed,
    )
    return model.fit(X, y)


def score(model, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def average_precision(y_true, scores) -> float:
    return average_precision_score(y_true, scores)


def save(model, info: dict, model_path: Path, info_path: Path) -> None:
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    Path(info_path).write_text(json.dumps(info, indent=2))
