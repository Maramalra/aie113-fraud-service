"""The business rule: what to do with a fraud score."""
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"    # let the payment through
    REVIEW = "review"  # send it to the fraud team with the reasons
    BLOCK = "block"    # stop it now, then the fraud team checks


def decide(score: float, review_threshold: float, block_threshold: float) -> Decision:
    """Score at or above block_threshold -> block; at or above review_threshold -> review."""
    if not 0.0 <= score <= 1.0:
        raise ValueError("a fraud score must be between 0 and 1")
    if not 0.0 < review_threshold <= block_threshold <= 1.0:
        raise ValueError("thresholds must satisfy 0 < review <= block <= 1")
    if score >= block_threshold:
        return Decision.BLOCK
    if score >= review_threshold:
        return Decision.REVIEW
    return Decision.ALLOW


def choose_threshold(precision_by_threshold: dict[float, float | None], min_precision: float) -> float:
    """The fraud team's rule: the LOWEST threshold where at least `min_precision` of alerts are fraud.

    `precision_by_threshold` maps each tried threshold to the share of its alerts that were fraud
    (None when it raised no alerts).
    """
    meeting = [t for t, p in precision_by_threshold.items() if p is not None and p >= min_precision]
    if not meeting:
        raise ValueError("No threshold meets the fraud team's rule; try a lower min_precision")
    return min(meeting)
