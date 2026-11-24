"""Data checks: the input data is what we expect. Needs data/creditcard.csv (`make train`)."""
import pandas as pd
import pytest

from fraud_service.config import Settings
from fraud_service.services import training

pytestmark = pytest.mark.model
COLUMNS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]


@pytest.fixture(scope="module")
def df():
    s = Settings()
    if not s.data_path.exists():
        pytest.skip("no data - run `make train`")
    return pd.read_csv(s.data_path)


def test_columns_are_present(df):
    assert list(df.columns) == COLUMNS


def test_values_are_sensible(df):
    assert not df.isna().any().any()
    assert set(df["Class"].unique()) == {0, 1}
    assert (df["Amount"] >= 0).all()
    assert df["Time"].between(0, 48 * 3600).all()
    assert 0.001 < df["Class"].mean() < 0.003        # fraud is rare, about 1 in 600


def test_no_future_data_in_training(df):
    s = Settings()
    train, valid, test = training.split_by_time(training.build_inputs(df), s.train_share, s.valid_share)
    assert train["Time"].max() <= valid["Time"].min()
    assert valid["Time"].max() <= test["Time"].min()
    assert len(train) + len(valid) + len(test) == len(df)
