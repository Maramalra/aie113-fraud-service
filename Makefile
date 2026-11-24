PY ?= .venv/bin/python

train:   ## download data (once), train the model, save into artifacts/
	$(PY) -m fraud_service.entrypoints.cli train

score:   ## score the example payment
	$(PY) -m fraud_service.entrypoints.cli score scripts/example_payment.json

golden:  ## Stage 1 proof: the service gives the notebook's answers
	$(PY) -m pytest tests/test_golden.py -v

test:
	$(PY) -m pytest -q
