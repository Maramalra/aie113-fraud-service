"""Adapter: send fraud alerts to a webhook. The token is used only in the Authorization header."""
import json
import logging
import urllib.request

from pydantic import SecretStr

log = logging.getLogger("fraud_service.alerts")


class WebhookAlertSender:
    def __init__(self, url: str, token: SecretStr) -> None:
        self._url = url
        self._token = token  # stays a SecretStr until the moment it is sent

    def send_block_alert(self, score: float, model_version: str, top_reason: str) -> None:
        # No payment values in the alert: only the score, model version and the reason's name.
        body = json.dumps({"event": "payment_blocked", "score": round(score, 4),
                           "model_version": model_version, "top_reason": top_reason}).encode()
        request = urllib.request.Request(self._url, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token.get_secret_value()}",
        })
        try:
            urllib.request.urlopen(request, timeout=2)
        except Exception as exc:  # an alert failure must never stop scoring
            log.warning("block alert not delivered: %s", type(exc).__name__)


class NoAlerts:
    """Used when no webhook is configured (local development, tests)."""

    def send_block_alert(self, score: float, model_version: str, top_reason: str) -> None:
        log.info("block alert (no webhook configured): score %.3f", score)
