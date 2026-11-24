"""All settings in one place. Override any of them with an environment variable FRAUD_<NAME>."""
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Values come from FRAUD_* environment variables, or from files in /run/secrets
    # (how Docker and Kubernetes hand secrets to a container).
    model_config = SettingsConfigDict(
        env_prefix="FRAUD_", extra="forbid",
        secrets_dir="/run/secrets" if Path("/run/secrets").is_dir() else None,
    )

    # Where things live
    data_url: str = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"
    data_path: Path = Path("data/creditcard.csv")
    model_path: Path = Path("artifacts/fraud_model.joblib")
    info_path: Path = Path("artifacts/model_info.json")

    # Training (same values as the notebook)
    model_version: str = "1.0.0"
    random_seed: int = 42
    train_share: float = 0.6
    valid_share: float = 0.2
    min_precision: float = 0.80  # fraud team's rule: >= 8 of every 10 alerts must be real fraud
    thresholds_to_try: list[float] = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
    amount_rule: float = 1000  # baseline: alert on every payment above this amount

    # Serving: the "review" threshold comes from the trained model; "block" is our business rule.
    # 0.9: on validation payments, 97% of alerts at 0.9 were real fraud (notebook table).
    block_threshold: float = 0.9
    top_reasons: int = 3

    # Alerting webhook that notifies the fraud team when a payment is BLOCKED.
    # The token is a SECRET: it comes from the environment (FRAUD_ALERT_WEBHOOK_TOKEN) or a mounted
    # secret file, never from code. SecretStr prints as '**********', so it cannot leak by accident.
    alert_webhook_url: str | None = None
    alert_webhook_token: SecretStr | None = None
