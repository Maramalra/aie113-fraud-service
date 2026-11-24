"""Model behaviour: how the REAL model behaves. Needs `make train` (uses data/ and artifacts/)."""
import pandas as pd
import pytest

from fraud_service.config import Settings
from fraud_service.domain.payment import FEATURE_NAMES, Payment
from fraud_service.services import training
from fraud_service.services.scoring import ScoringService

from .conftest import GOLDEN

pytestmark = pytest.mark.model

# Agreed quality floor on the test period (the model got 75% / 86%; floors leave room for
# small library differences but would catch a model that silently got worse).
MIN_SHARE_OF_FRAUDS_CAUGHT = 0.70
MIN_SHARE_OF_ALERTS_THAT_ARE_FRAUD = 0.80


@pytest.fixture(scope="module")
def test_period():
    s = Settings()
    if not s.data_path.exists():
        pytest.skip("no data - run `make train`")
    df = training.build_inputs(pd.read_csv(s.data_path))
    return training.split_by_time(df, s.train_share, s.valid_share)[2]


def golden_payment(name):
    return next(c["payment"] for c in GOLDEN["cases"] if c["name"] == name)


def test_quality_on_reference_payments_stays_above_the_agreed_floor(real_model, test_period):
    scores = pd.Series(real_model.score_many(test_period[list(FEATURE_NAMES)].to_dict("records")))
    alert = scores.to_numpy() >= real_model.review_threshold
    y = test_period["Class"].to_numpy()
    caught = (alert & (y == 1)).sum()
    assert caught / y.sum() >= MIN_SHARE_OF_FRAUDS_CAUGHT
    assert caught / alert.sum() >= MIN_SHARE_OF_ALERTS_THAT_ARE_FRAUD


def test_model_beats_the_amount_rule_baseline(real_model, test_period):
    y = test_period["Class"].to_numpy()
    rule_caught = ((test_period["Amount"].to_numpy() > 1000) & (y == 1)).sum()
    scores = real_model.score_many(test_period[list(FEATURE_NAMES)].to_dict("records"))
    model_caught = ((pd.Series(scores).to_numpy() >= real_model.review_threshold) & (y == 1)).sum()
    assert model_caught > 5 * rule_caught


@pytest.mark.parametrize("name", ["caught_fraud", "false_alarm", "notebook_last_cell"])
def test_making_the_top_reason_typical_lowers_the_score(real_model, name):
    service = ScoringService(real_model, block_threshold=0.9)
    record = golden_payment(name)
    before = service.assess(Payment.from_record(record))
    top = before.reasons[0]
    after = service.assess(Payment.from_record({**record, top.feature: top.typical}))
    assert after.score < before.score


def test_invariance_same_hour_next_day_gives_the_same_score(real_model):
    service = ScoringService(real_model, block_threshold=0.9)
    record = golden_payment("caught_fraud")
    a = service.assess(Payment.from_record(record))
    b = service.assess(Payment.from_record({**record, "Time": record["Time"] + 24 * 3600}))
    assert a.score == b.score


def test_scores_are_repeatable_and_in_range(real_model):
    service = ScoringService(real_model, block_threshold=0.9)
    p = Payment.from_record(golden_payment("normal_a"))
    first, second = service.assess(p), service.assess(p)
    assert first == second and 0.0 <= first.score <= 1.0
