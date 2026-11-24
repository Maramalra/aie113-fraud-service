"""Save the NOTEBOOK's answers for 5 real payments (Stage 1 golden check).

Uses the notebook's own model file and its own `what_if_typical` code (copied verbatim),
so the refactored service can later prove it gives the same answers.
Run from the repo root after running notebook/notebook.ipynb:
    python scripts/make_golden.py
"""
import json
from pathlib import Path

import joblib
import pandas as pd

NB = Path("notebook")
model = joblib.load(NB / "artifacts/fraud_model.joblib")
info = json.loads((NB / "artifacts/model_info.json").read_text())
FEATURES = info["features"]
TYPICAL = pd.Series(info["typical_values"])


def what_if_typical(model, features_row, typical):  # verbatim from the notebook
    base_score = model.predict_proba(pd.DataFrame([features_row]))[0, 1]
    variants = pd.DataFrame([features_row] * len(features_row))
    for i, name in enumerate(features_row.index):
        variants.iloc[i, i] = typical[name]
    new_scores = model.predict_proba(variants)[:, 1]
    reasons = pd.DataFrame({
        "value": features_row.values,
        "typical": typical[features_row.index].values,
        "score if typical": new_scores,
        "drop": base_score - new_scores,
    }, index=features_row.index)
    return base_score, reasons.sort_values("drop", ascending=False)


# Same data preparation as the notebook
df = pd.read_csv(NB / "data/creditcard.csv")
df = df.sort_values("Time", kind="stable").reset_index(drop=True)

# 229712 = first caught fraud, 228505 = first false alarm (both shown in the notebook),
# 228000 and 250000 = ordinary payments from the test period.
picks = {"caught_fraud": 229712, "false_alarm": 228505, "normal_a": 228000, "normal_b": 250000}
payments = {k: df.loc[i, ["Time", "Amount"] + [f"V{j}" for j in range(1, 29)]].astype(float).to_dict()
            for k, i in picks.items()}
# The payment written out in the notebook's last cell
payments["notebook_last_cell"] = {"Time": 154278.0, "Amount": 1504.93, **{
    f"V{i}": v for i, v in enumerate([
        -1.60021129907252, -3.48813018118561, -6.45930280667571, 3.24681566349703, -1.61460769860713,
        -1.26037454854632, 0.288223321921388, -0.0489639910109505, -0.734974617920653, -4.44148408070017,
        2.94437484242405, -3.80546898374331, -2.10222683492697, -6.1061832734711, -0.641736399701777,
        -1.55596289626148, -2.08406707082134, 0.394247352869229, 0.0833797227600835, 3.18935489592753,
        1.19117480721903, -0.96714144500067, -1.46342052446637, -0.624230851495284, -0.176461532068143,
        0.400348351070197, 0.152946864261687, 0.477774924576796], start=1)}}

cases = []
for name, p in payments.items():
    feats = dict(p)
    feats["hour"] = (feats["Time"] // 3600) % 24
    row = pd.DataFrame([feats])[FEATURES]
    score, reasons = what_if_typical(model, row.iloc[0], TYPICAL)
    cases.append({
        "name": name,
        "payment": p,
        "expected_score": float(score),
        "expected_alert": bool(score >= info["threshold"]),
        "expected_top_reasons": [
            {"feature": f, "score_if_typical": float(r["score if typical"])}
            for f, r in reasons.head(3).iterrows()
        ],
    })
    print(f"{name:20s} score {score:.6f}  top reasons {list(reasons.head(3).index)}")

out = Path("tests/golden/notebook_answers.json")
out.write_text(json.dumps({"threshold": info["threshold"], "cases": cases}, indent=2))
print("saved", out)
