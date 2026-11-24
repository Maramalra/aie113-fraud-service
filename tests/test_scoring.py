"""Unit: the scoring service with a fake model (known behaviour)."""
import pytest

from fraud_service.domain.decision import Decision
from fraud_service.domain.payment import FEATURE_NAMES, Payment
from fraud_service.services.scoring import ScoringService

from .fakes import FakeModel, payment


def assess(**overrides):
    return ScoringService(FakeModel(), block_threshold=0.9).assess(Payment.from_record(payment(**overrides)))


def test_the_input_that_drives_the_score_is_the_top_reason():
    result = assess(V14=-6.0)            # fake score depends only on V14
    assert result.score == pytest.approx(0.6) and result.decision == Decision.REVIEW
    assert result.reasons[0].feature == "V14"
    assert result.reasons[0].score_if_typical == 0.0


def test_reasons_always_name_real_inputs_and_are_strongest_first():
    result = assess(V14=-9.0)
    assert all(r.feature in FEATURE_NAMES for r in result.reasons)
    drops = [result.score - r.score_if_typical for r in result.reasons]
    assert drops == sorted(drops, reverse=True)
    assert len(result.reasons) == 3
