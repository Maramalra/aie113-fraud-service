# Fraud service · SDA-AIE-113 group project (Fraud track)

A card-fraud scoring service built from the course's starter notebook (`notebook/`), stage by stage,
following [GUIDE.md](GUIDE.md). The model is explained in plain words in [notebook/README.md](notebook/README.md).
Our progress and what we learned is in [JOURNAL.md](JOURNAL.md).

## Quick start

    python3 -m venv .venv && .venv/bin/pip install -e . -r requirements.txt
    make train     # downloads the data once (150 MB), trains, saves artifacts/ (~5 s)
    make score     # scores scripts/example_payment.json
    make test      # runs the tests

## Structure (Stage 1: clean architecture)

    src/fraud_service/
      config.py      All settings in one place (override with FRAUD_<NAME> env vars).
      domain/        The words and rules of fraud: Payment, Decision (allow/review/block),
                     the threshold rule, Reason. Pure Python: imports no pandas, sklearn or web.
      services/      The jobs: scoring.py ("score this payment + top reasons"),
                     training.py ("train, choose threshold, measure"). Talk to the model through a port.
      adapters/      The tools: sklearn_model.py (scikit-learn + joblib), csv_data.py (download/read data).
      entrypoints/   How the world starts a job: cli.py (command line); api.py comes in Stage 2.
    tests/golden/    The notebook's answers for 5 payments; the service must give the same.
    scripts/         make_golden.py (saves the notebook's answers), example_payment.json.
    notebook/        The original starter notebook, untouched, for reference.

Import directions (inner never imports outer):

    entrypoints -> services -> domain
    entrypoints -> adapters        (adapters implement the domain's FraudModel port)
    services    -> config

Replace the model library -> only `adapters/sklearn_model.py` changes.
Replace the data source   -> only `adapters/csv_data.py` changes.
Change the alert rule     -> `domain/decision.py` (the rule) or `config.py` (the numbers).

Teaching project on 2013 data: never use it to block real cards or judge people.
