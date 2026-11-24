"""What the service answers about one payment."""
from dataclasses import dataclass

from .decision import Decision


@dataclass(frozen=True)
class Reason:
    """'If this input were typical, the score would fall to score_if_typical.'"""

    feature: str
    value: float
    typical: float
    score_if_typical: float


@dataclass(frozen=True)
class Assessment:
    score: float
    decision: Decision
    review_threshold: float
    block_threshold: float
    model_version: str
    reasons: tuple[Reason, ...]
