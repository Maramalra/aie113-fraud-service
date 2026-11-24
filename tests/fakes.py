"""A stand-in model with known behaviour, so fast tests do not need the real one."""
from fraud_service.domain.payment import FEATURE_NAMES


class FakeModel:
    """Score = 0.1 * how far V14 is below 0, capped to 0..1. Typical V14 is 0."""

    version = "fake-1"
    feature_names = list(FEATURE_NAMES)
    typical_values = {name: 0.0 for name in FEATURE_NAMES}
    review_threshold = 0.4

    def score_many(self, rows):
        return [min(1.0, max(0.0, -0.1 * row["V14"])) for row in rows]


def payment(**overrides) -> dict:
    p = {"Time": 3600.0 * 10, "Amount": 50.0, **{f"V{i}": 0.0 for i in range(1, 29)}}
    p.update(overrides)
    return p
