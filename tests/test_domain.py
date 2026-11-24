"""Unit: the business rules alone, in milliseconds."""
import pytest

from fraud_service.domain.decision import Decision, choose_threshold, decide
from fraud_service.domain.payment import FEATURE_NAMES, Payment

from .fakes import payment


@pytest.mark.parametrize("score, expected", [
    (0.0, Decision.ALLOW), (0.399999, Decision.ALLOW),
    (0.4, Decision.REVIEW), (0.899999, Decision.REVIEW),   # flips EXACTLY at the threshold
    (0.9, Decision.BLOCK), (1.0, Decision.BLOCK),
])
def test_decision_flips_exactly_at_the_thresholds(score, expected):
    assert decide(score, review_threshold=0.4, block_threshold=0.9) == expected


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_impossible_scores_are_rejected(score):
    with pytest.raises(ValueError):
        decide(score, 0.4, 0.9)


def test_block_threshold_cannot_be_below_review():
    with pytest.raises(ValueError):
        decide(0.5, review_threshold=0.9, block_threshold=0.4)


def test_threshold_rule_picks_the_lowest_meeting_the_team_rule():
    # values from the notebook's validation table (precision per threshold)
    table = {0.01: 0.45, 0.1: 0.69, 0.3: 0.77, 0.4: 0.80, 0.5: 0.80, 0.9: 0.97, 0.99: None}
    assert choose_threshold(table, min_precision=0.80) == 0.4


def test_threshold_rule_fails_loudly_when_nothing_qualifies():
    with pytest.raises(ValueError):
        choose_threshold({0.1: 0.5, 0.5: None}, min_precision=0.8)


@pytest.mark.parametrize("time, hour", [(0, 0), (3599, 0), (3600, 1), (86399, 23), (86400, 0), (154278, 18)])
def test_hour_of_day_is_built_like_the_notebook(time, hour):
    assert Payment.from_record(payment(Time=time)).hour == hour


def test_features_are_in_the_trained_order():
    assert list(Payment.from_record(payment()).features()) == list(FEATURE_NAMES)


@pytest.mark.parametrize("bad", [dict(Amount=-1.0), dict(Time=-1.0)])
def test_impossible_payments_are_rejected(bad):
    with pytest.raises(ValueError):
        Payment.from_record(payment(**bad))


def test_a_payment_needs_28_v_values():
    with pytest.raises(ValueError):
        Payment(time=0, amount=1, v=(0.0,) * 27)
