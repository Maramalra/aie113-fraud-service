# Project journal · سجل المشروع

**Group · المجموعة:** _(names)_ — AI coding agent: Claude Code (Claude Opus 5.5)
**Track · المسار:** fraud
**Repository · المستودع:** _(link)_

---

## Stage 0: Track and model · المسار والنموذج

**What we asked the agent**
Read AGENTS.md, GUIDE.md and the fraud README; explain the model in plain words.

**What it built**
Nothing yet. We ran `notebook.ipynb` top to bottom in Colab (Runtime → Run all).

**What we checked, and what we saw**
- 284,807 payments, 492 frauds (0.173%). Always answering "not fraud" is right 99.83% of the time and catches 0.
- Split by time: train 170,884 (hours 0–33.4), validation 56,961, test 56,962 (75 frauds).
- Trained in 8.8 s. Threshold 0.4 = lowest where ≥ 80% of validation alerts are real fraud.
- Test: model catches 56 of 75 frauds (74.7%); 83.6% of its alerts are real fraud; 11 false alarms.
  Baselines: "always not fraud" catches 0; "amount > 1000" catches 2 of 75.
- Top reasons for fraud 229712: V10 and V14 (setting either to typical drops the score from 0.995 to < 0.1).

**What surprised us or went wrong**
Colab gave 67 alerts, the README says 65. The README explains it: a different scikit-learn version. Locally,
with the workshop's pinned scikit-learn 1.9.1, we get exactly 65 (86.2% of alerts are fraud).
Also: "accuracy" is useless here — doing nothing scores 99.87%.

**How we would explain this stage to a colleague**
The model gives each card payment a fraud score from 0 to 1. At 0.4 or above it alerts the fraud team and
says which inputs pushed the score up ("what if this value were typical?"). It learned from the past
(first 60% of time) and was judged on the future (last 20%). It catches 3 of 4 frauds, and about 6 of 7
alerts are real fraud. We judge it by those two numbers, not accuracy.

**Open questions**
What do V1–V28 really mean? Only the bank knows.

---

## Stage 1: Clean architecture · المعمارية النظيفة

**What we asked the agent**
Propose a structure; before moving code, save the notebook's answers for 5 payments; prove the new code
gives the same answers.

**What it built**
- `src/fraud_service/domain/` — `payment.py` (a Payment and how it becomes inputs, incl. hour of day),
  `decision.py` (allow/review/block rule; "lowest threshold with ≥ 80% precision" rule), `assessment.py`
  (Reason, Assessment), `ports.py` (FraudModel: anything that can score). Imports only standard Python.
- `services/scoring.py` — score one payment, decide, top 3 reasons ("what if typical?").
- `services/training.py` — the notebook's training steps: split by time, train, choose threshold, measure.
- `adapters/sklearn_model.py` — the only file that knows scikit-learn/joblib. `adapters/csv_data.py` — data download.
- `entrypoints/cli.py` — `make train`, `make score`.
- `config.py` — all settings in one place (FRAUD_ env vars). New: `block_threshold = 0.9`.
- `scripts/make_golden.py` + `tests/golden/notebook_answers.json` — the notebook's answers.

**What we checked, and what we saw**
- Golden check (`make golden`): 5 of 5 payments (caught fraud, false alarm, two normal, notebook's last
  cell) give the same score and the same top 3 reasons as the notebook, to 9 decimals.
- Retraining with the new code (3.8 s) gives identical threshold, typical values and test metrics.
- `grep` on `domain/`: only `dataclasses`, `enum`, `typing` imports.
- Broke on purpose: _(to do with the group: e.g. change `hour` to `Time // 60` and watch `make golden` fail)_

**What surprised us or went wrong**
Python from python.org could not download the data (SSL certificate error); we downloaded the CSV with curl.

**How we would explain this stage to a colleague**
We split the notebook into rooms: domain (fraud words and rules, no tools), services (jobs like "score this
payment"), adapters (scikit-learn, the CSV file) and entry points (command line, later the API), with
settings in one file. Inner rooms never import outer ones, so replacing scikit-learn only changes one
adapter file. We proved nothing broke by saving the notebook's answers first and checking the new code
gives the same ones.

**Why this architecture**
Clean architecture as taught in Module 1; the fraud README says the threshold is a business rule and the
reasons are part of the job, so both live in the domain/services, not in the model adapter.

**Open questions**
Is 0.9 the right "block" level? We chose it because 97% of validation alerts at 0.9 were real fraud.

---

## Stage 2: FastAPI endpoint · نقطة نهاية FastAPI

**What we asked the agent**
Design the request and response first; one safe error shape; health vs readiness; load the model once.

**What it built**
- `entrypoints/api.py` — `POST /v1/score`, `GET /health/live`, `GET /health/ready`, docs at `/docs`.
  The contract (pydantic): `Time`, `Amount` (≥ 0), `V1`…`V28` all required numbers; unknown fields,
  NaN/infinity rejected. The model is loaded once at start-up (lifespan). Decisions: allow < 0.4 ≤ review < 0.9 ≤ block.
- `tests/test_api.py` + `tests/fakes.py` — API tests with a fake model (no real model needed, < 1 s).
- `make serve`.

**What we checked, and what we saw**
Good request (the notebook's last-cell payment) →
`{"score": 0.9989, "decision": "block", "review_threshold": 0.4, "block_threshold": 0.9,
"reasons": [V14 → 0.149, V10 → 0.278, V4 → 0.983], ...}` — same as the notebook.
Bad request (V14 missing, Amount −5, V1 "abc") →
`422 {"error": {"code": "invalid_payment", "details": [{"field": "Amount", "problem": "Input should be greater than or equal to 0"}, {"field": "V1", ...}, {"field": "V14", "problem": "Field required"}]}}`
— the values we sent are never echoed. A smuggled `card_number` field is rejected without echoing the number.
Readiness checks that the model and its facts were loaded; with the model file missing, `/health/live` is
200 but `/health/ready` is 503 and `/v1/score` answers `not_ready`.

**What surprised us or went wrong**
FastAPI's default error message repeats the input value back. We replaced it with our own error shape so
private payment data never leaks into an error.

**How we would explain this stage to a colleague**
The API is the only door to our model. It checks every request against a contract and rejects bad ones
with a clear, safe error. Live means "the process runs"; ready means "the model is loaded and can score".
The URL has `/v1` so we can change the contract later without breaking current users.
