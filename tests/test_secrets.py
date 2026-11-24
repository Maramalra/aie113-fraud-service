"""The alert-webhook token (a secret) never appears in settings output, logs, errors or alerts' bodies."""
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from fraud_service.adapters.log_masking import MaskSecretsFilter
from fraud_service.config import Settings
from fraud_service.domain.payment import Payment
from fraud_service.entrypoints.api import create_app
from fraud_service.services.scoring import ScoringService

from .fakes import FakeModel, payment

FAKE_TOKEN = "fake-practice-token-not-real-123"  # a FAKE value, for practice only


def test_the_token_comes_from_the_environment_and_prints_masked(monkeypatch):
    monkeypatch.setenv("FRAUD_ALERT_WEBHOOK_TOKEN", FAKE_TOKEN)
    s = Settings()
    assert s.alert_webhook_token.get_secret_value() == FAKE_TOKEN
    assert FAKE_TOKEN not in str(s) and FAKE_TOKEN not in repr(s.model_dump())


def test_the_token_never_reaches_the_logs(monkeypatch, caplog):
    monkeypatch.setenv("FRAUD_ALERT_WEBHOOK_TOKEN", FAKE_TOKEN)
    with caplog.at_level(logging.INFO), TestClient(create_app(Settings(), model=FakeModel())) as c:
        c.post("/v1/score", json=payment(V14=-9.5))
        c.post("/v1/score", json=payment(V1="bad"))
    assert "settings_effective" in caplog.text
    assert FAKE_TOKEN not in caplog.text


def test_the_mask_catches_a_token_logged_by_mistake():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "oops token=%s", (FAKE_TOKEN,), None)
    MaskSecretsFilter([FAKE_TOKEN]).filter(record)
    assert record.getMessage() == "oops token=**********"


class RecordingAlerts:
    def __init__(self):
        self.sent = []

    def send_block_alert(self, score, model_version, top_reason):
        self.sent.append((score, top_reason))


def test_only_blocked_payments_alert_the_fraud_team():
    alerts = RecordingAlerts()
    service = ScoringService(FakeModel(), block_threshold=0.9, alerts=alerts)
    service.assess(Payment.from_record(payment(V14=-5.0)))   # review: no alert
    service.assess(Payment.from_record(payment(V14=-9.5)))   # block: alert
    assert len(alerts.sent) == 1
    assert alerts.sent[0] == (pytest.approx(0.95), "V14")


def test_secretstr_hides_the_value():
    assert str(SecretStr(FAKE_TOKEN)) == "**********"
