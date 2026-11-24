"""What the domain needs from the outside world, described without naming any tool."""
from typing import Protocol, Sequence


class FraudModel(Protocol):
    """Anything that can score payments. The scikit-learn adapter is one; a fake is another."""

    version: str
    feature_names: Sequence[str]
    typical_values: dict[str, float]
    review_threshold: float

    def score_many(self, rows: Sequence[dict[str, float]]) -> list[float]:
        """Fraud scores (0..1) for many input rows, each a {feature name: value} dict."""
        ...
