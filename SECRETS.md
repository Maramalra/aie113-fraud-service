# Secrets in this project

**The secret:** `FRAUD_ALERT_WEBHOOK_TOKEN`, the token for the webhook that tells the fraud team a payment
was **blocked**. (For practice: our tests only ever use fake values.)

**The rules:** never in git, never in the image, never in a log. If it leaks: **rotate first**.

## The path of the secret

| Where | How it gets the token | What protects it |
|---|---|---|
| Created | By whoever owns the alerting system (the fraud team's tool), short-lived, can only post alerts | Least privilege, expiry |
| Developer laptop | `.env` file (git-ignored, template `.env.example`) or a secrets-manager CLI that injects it at run time | `.gitignore`, `.dockerignore` |
| Pipeline (GitHub Actions) | A GitHub **environment secret** (`production` environment, needs a reviewer's approval); the image is pushed with the short-lived `GITHUB_TOKEN`, no stored passwords | Masked in logs, approval gate |
| Running container | Environment variable `FRAUD_ALERT_WEBHOOK_TOKEN`, or a file in `/run/secrets/` (Docker/Kubernetes secret, or synced from a cloud secret store) — read once at start-up | Not baked into the image |
| Inside the code | `pydantic.SecretStr` — prints as `**********`; only `adapters/alerts.py` reveals it, in the HTTP header | Typed settings |
| Logs | `adapters/log_masking.py` replaces the token with `**********` in every log line (safety net) | Masking filter |
| Every push | **gitleaks** scans the whole git history in CI; GitHub push protection blocks known key formats | Secret scanning |

## How we checked
- `tests/test_secrets.py`: the token comes from the environment, prints masked, never reaches the logs (even when
  logged by mistake), and only *blocked* payments send an alert.
- Running the service with a fake token: the start-up log shows `'alert_webhook_token': SecretStr('**********')`,
  and the token appears 0 times in the log.
- `.dockerignore` excludes `.env` and key files, so they cannot be copied into the image.

## Incident plan (if the token leaks)
1. **Rotate** — revoke the token in the alerting system and create a new one (minutes, not hours).
2. **Replace** — put the new token in the GitHub environment secret and the server's secret store; restart.
3. **Check** — look at the alerting system's logs for use of the old token since the leak.
4. **Clean** — remove it from the code/history (rewrite history if it was pushed) — only *after* rotating.
5. **Prevent** — add a test or scanner rule that would have caught it; write down what happened.

## Next step: SOPS + age (encrypted secrets in the repo)
Each member makes an age key pair (`age-keygen`); public keys go in `.sops.yaml`; `sops -e secrets.enc.yaml`
encrypts only the values, so the file stays reviewable while the token is unreadable. Private keys
(`*.agekey`, `keys.txt`) are git-ignored. Requires the `sops` and `age` tools.
