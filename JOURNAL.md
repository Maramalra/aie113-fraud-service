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

---

## Stage 3: Container · الحاوية

**What we asked the agent**
A small, safe image: multi-stage, locked versions, non-root, health check, one-command start; decide where the model lives.

**What it built**
- `Dockerfile` — two stages. *builder*: installs the exact library versions (`requirements.txt`), downloads the
  data, and **trains the model with our own code during the build**. *runtime*: `python:3.12-slim` with only the
  libraries, our code and the trained model (no data, no tests, no build tools). Runs as user `app` (uid 10001).
  `HEALTHCHECK` calls `/health/ready` every 15 s.
- `.dockerignore` — keeps `.git`, `data/`, `.env`, key files out of the build.
- `compose.yaml` — `docker compose up --build` starts the service on port 8000, read-only file system.
- `scripts/smoke_test.sh` — starts the image, waits for "healthy", checks the user is not root, scores a payment.

**Where the model lives, and why:** inside the image, trained during the build. One image = one exact model,
so an update is all-or-nothing and the service never depends on a download at start-up. The cost: every
rebuild of the code layer retrains (~12 s in CI). The model is small (600 KB), so this is fine.

**What we checked, and what we saw**
Docker is not installed on our laptop yet, so the image is built and smoke-tested by GitHub Actions (Stage 5):
- Build in CI: 1 min 32 s for the whole job (training inside the build: 12 s). The image: **157 MB** compressed
  (688 MB unpacked; most of it is scikit-learn, scipy, numpy and pandas).
- Smoke test output: `health: healthy`, `user inside the container: app` (not root), and the container scores the
  notebook's payment at **0.998861 → block**, top reason V14 — the same answer as the notebook.
- To try locally once Docker Desktop is installed: `make image`, `make smoke`, or `docker compose up --build`
  then open http://localhost:8000/docs. Note the rebuild time after changing one line of code.

**What surprised us or went wrong**
The first CI build succeeded but the job failed while *saving the build cache* (GitHub's cache answered 504,
it timed out uploading the 150 MB data layer). Fix: cache only the final image's layers, and never fail the
build because of the cache. We did not weaken any check.

**How we would explain this stage to a colleague**
A container packs our service with everything it needs, so it runs the same on any machine. The image is the
recipe result; a container is a running copy. We build in two rooms so the final image carries only what is needed
to run, as a normal user, and Docker checks it is ready by calling our readiness endpoint.

---

## Stage 4: Tests · الاختبارات

**What we asked the agent**
List the tests by level first; use a fake model for fast tests; break something on purpose.

**What it built** (56 tests, ~2 s)
| Level | File | What it protects |
|---|---|---|
| Unit | `test_domain.py` | Decision flips **exactly** at 0.4 and 0.9; impossible scores/payments rejected; the threshold rule picks the lowest threshold with ≥ 80% precision; hour of day built like the notebook; inputs in the trained order |
| Unit | `test_scoring.py` | With a fake model: the input that drives the score is the top reason; reasons name real inputs, strongest first |
| Integration | `test_api.py` | Good request gets the promised shape (allow/review/block); 7 kinds of bad request get one error shape; errors never echo values; not ready when the model is missing |
| Golden | `test_golden.py` | 5 payments give the notebook's scores and top reasons |
| Model behaviour | `test_model_behaviour.py` | On the 56,962 test payments: ≥ 70% of frauds caught and ≥ 80% of alerts are fraud; beats the "amount > 1000" rule; making the top reason typical lowers the score; same hour next day = same score; repeatable |
| Data checks | `test_data.py` | Columns present; no missing values; Class is 0/1; amounts ≥ 0; fraud share ≈ 0.17%; no future data in training |
| Secrets | `test_secrets.py` | (Stage 6) |
| Smoke | `scripts/smoke_test.sh` | The container starts, is healthy, is not root, and scores a payment |

`pytest -m "not model"` runs the 36+ fast tests (fake model) in under 1 s; the rest need `make train`.

**What we checked, and what we saw**
- All tests pass; coverage 73% before Stage 6 (untested: the CLI and the CSV download — they run in CI's training step).
- **Deliberate break:** we changed the hour to `Time // 60` (minutes instead of hours). **8 tests failed**: 3 unit
  tests (hour built like the notebook) and all 5 golden tests. Undone → all pass.
- Which tests catch a model that *silently got worse*? The quality floor, the baseline comparison, and the golden tests.

**What surprised us or went wrong**
Two of the agent's own tests first failed because `0.1 × 6` is `0.6000000000000001` in a computer. The fix was
to compare with `pytest.approx` (the service was right, the test was too strict about decimals) — not to delete the test.

**How we would explain this stage to a colleague**
Tests are small automatic checks. Unit tests check one rule in milliseconds; integration tests use the API like a
client; golden tests make sure answers did not change; model-behaviour tests check the real model still catches
fraud well and gives sensible reasons; data checks make sure the data is what we expect. A fake model keeps most
tests fast.

---

## Stage 5: GitHub Actions · خط التشغيل الآلي

**What we asked the agent**
A pipeline with lint, test, image build, smoke test and publish; least permissions; pinned actions.

**What it built** — `.github/workflows/ci.yml`, on every push to `main` and every pull request:
1. **lint** — `ruff` (style and simple mistakes).
2. **secret-scan** — `gitleaks` over the whole history (Stage 6).
3. **test** — fast tests, then download data (cached), train, all tests with coverage.
4. **image** — build the Docker image, show its size, run the smoke test.
5. **publish** — only on `main`, only after everything passes: push to `ghcr.io/maramalra/aie113-fraud-service`.

Permissions: read-only by default; only *publish* gets `packages: write`, using GitHub's short-lived `GITHUB_TOKEN`
(no stored password). Every action is pinned to an exact commit SHA (a moved tag cannot change what runs —
the course's Trivy supply-chain example).

**What we checked, and what we saw**
Pull request #3 run: lint ✅ 14 s · test ✅ 45 s (download + train + all tests) · image ✅ 1 m 32 s
(build + smoke test) · publish ⏭ skipped (only runs on `main`, as designed).
**To do in the GitHub website (us):** Settings → Branches → Add branch ruleset for `main`: require a pull request,
require status checks `lint`, `secret-scan`, `test`, `image` to pass. Then open a PR with a failing test, screenshot
the blocked merge button, fix it, merge.

**What surprised us or went wrong**
GitHub refused to accept the workflow file at first: our `gh` login lacked the `workflow` permission
(`gh auth refresh -s workflow` fixed it). Then the cache 504 described in Stage 3.

**How we would explain this stage to a colleague**
The pipeline is an automatic checklist that runs on every change. People forget steps; the pipeline never does.
With branch protection, nothing reaches `main` unless lint, secret scan, tests and the container smoke test are green.

---

## Stage 6: Secrets · الأسرار

**What we asked the agent**
A realistic secret (alert-webhook token) handled the modern way; prove it never leaks; scanning; incident plan.

**What it built**
- `config.py` — `alert_webhook_token: SecretStr`, read from `FRAUD_ALERT_WEBHOOK_TOKEN` or `/run/secrets/` (Docker/Kubernetes secret files).
- `adapters/alerts.py` — posts to the webhook **only for blocked payments**; the token only goes in the HTTP header;
  the alert body has no payment values.
- `adapters/log_masking.py` — replaces the token with `**********` in every log line (safety net).
- `.env.example` (template; `.env` is git-ignored and docker-ignored), `.gitleaks.toml`, gitleaks job in CI.
- `SECRETS.md` — the path of the secret and the incident plan.

**The path of our secret**
Created by the alerting system's owner (short-lived, can only post alerts) → laptop: git-ignored `.env` →
pipeline: GitHub environment secret with approval → running container: env var or `/run/secrets` file from a
secret store → code: `SecretStr` → logs: masked. Never in git, never in the image.

**What we checked, and what we saw**
- `tests/test_secrets.py` (5 tests): masked when printed; 0 times in the logs during real requests; masked even when
  logged by mistake (`oops token=**********`); only *block* decisions alert.
- Running the service with a fake token: start-up log shows `'alert_webhook_token': SecretStr('**********')`;
  the token appears **0 times** in the log.
- gitleaks in CI: SCAN_RESULT

**Incident plan (five lines)**
1. Rotate: revoke the token and create a new one. 2. Replace it in the GitHub environment and the secret store; restart.
3. Check the alerting system's logs for use of the old token. 4. Clean it from code/history — only after rotating.
5. Prevent: add a scanner rule or test that would have caught it.

**How we would explain this stage to a colleague**
A secret grants access, so it lives only where it is needed and is never written into git, the image or logs. Our
code reads it from the environment, keeps it wrapped so printing shows stars, and a scanner checks every push.
If it ever leaks, we rotate it first, because deleting a leaked secret does not remove the copies.

**Open questions**
SOPS + age (encrypted secrets inside the repo) is described in `SECRETS.md` as our next step; it needs the
`sops` and `age` tools installed.
