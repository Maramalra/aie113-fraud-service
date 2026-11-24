"""Golden check: the service gives the SAME answers the notebook gave (saved in Stage 1)."""
import pytest

from fraud_service.domain.payment import Payment
from fraud_service.services.scoring import ScoringService

from .conftest import GOLDEN

pytestmark = pytest.mark.model


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["name"])
def test_same_answers_as_notebook(real_model, case):
    result = ScoringService(real_model, block_threshold=0.9).assess(Payment.from_record(case["payment"]))

    assert result.score == pytest.approx(case["expected_score"], abs=1e-9)
    assert (result.score >= GOLDEN["threshold"]) == case["expected_alert"]
    assert [r.feature for r in result.reasons] == [r["feature"] for r in case["expected_top_reasons"]]
    for got, want in zip(result.reasons, case["expected_top_reasons"], strict=True):
        assert got.score_if_typical == pytest.approx(want["score_if_typical"], abs=1e-9)
