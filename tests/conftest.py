import json
from pathlib import Path

import pytest

from fraud_service.config import Settings

GOLDEN = json.loads((Path(__file__).parent / "golden/notebook_answers.json").read_text())


@pytest.fixture(scope="session")
def real_model():
    """The real trained model from artifacts/. Skips if `make train` has not been run."""
    from fraud_service.adapters.sklearn_model import SklearnFraudModel

    s = Settings()
    if not s.model_path.exists():
        pytest.skip("no trained model in artifacts/ - run `make train`")
    return SklearnFraudModel.load(s.model_path, s.info_path)
