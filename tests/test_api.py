"""Integration: the API from the outside, like a real client (fake model, fast)."""
import pytest
from fastapi.testclient import TestClient

from fraud_service.config import Settings
from fraud_service.entrypoints.api import create_app

from .fakes import FakeModel, payment


@pytest.fixture
def client():
    with TestClient(create_app(Settings(), model=FakeModel())) as c:
        yield c


def test_health(client):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready", "model_version": "fake-1"}


@pytest.mark.parametrize("v14, decision", [(0.0, "allow"), (-5.0, "review"), (-9.5, "block")])
def test_good_request_gets_the_promised_shape(client, v14, decision):
    r = client.post("/v1/score", json=payment(V14=v14))
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == decision
    assert set(body) == {"score", "decision", "review_threshold", "block_threshold", "model_version",
                         "reasons", "note"}
    assert len(body["reasons"]) == 3


@pytest.mark.parametrize("bad", [
    {k: v for k, v in payment().items() if k != "V14"},      # missing field
    payment(Amount=-1),                                        # negative amount
    payment(Time=-10),                                         # negative time
    payment(V1="abc"),                                         # not a number
    payment(V2=None),                                          # null
    payment(card_number="4111111111111111"),                   # unknown field
    {},                                                         # empty
])
def test_bad_requests_are_rejected_with_one_error_shape(client, bad):
    r = client.post("/v1/score", json=bad)
    assert r.status_code == 422
    assert set(r.json()) == {"error"}
    assert r.json()["error"]["code"] == "invalid_payment"


def test_errors_never_echo_the_values_sent(client):
    r = client.post("/v1/score", json=payment(card_number="4111111111111111", V1="secret-ish-text"))
    assert "4111111111111111" not in r.text
    assert "secret-ish-text" not in r.text


def test_not_ready_when_the_model_cannot_load(tmp_path):
    settings = Settings(model_path=tmp_path / "missing.joblib", info_path=tmp_path / "missing.json")
    with TestClient(create_app(settings)) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503
        assert c.post("/v1/score", json=payment()).json()["error"]["code"] == "not_ready"
