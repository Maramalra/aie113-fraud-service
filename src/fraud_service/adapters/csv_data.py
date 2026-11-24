"""Adapter: get the payments data (download once, then read the CSV)."""
import os
import urllib.request
from pathlib import Path

import pandas as pd


def load_payments(path: Path, url: str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print("Downloading", url)
        urllib.request.urlretrieve(url, str(path) + ".part")
        os.replace(str(path) + ".part", path)
    df = pd.read_csv(path)
    df["Class"] = df["Class"].astype(int)
    return df
