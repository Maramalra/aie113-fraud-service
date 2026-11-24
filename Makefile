PY ?= .venv/bin/python

train:   ## download data (once), train the model, save into artifacts/
	$(PY) -m fraud_service.entrypoints.cli train

score:   ## score the example payment
	$(PY) -m fraud_service.entrypoints.cli score scripts/example_payment.json

golden:  ## Stage 1 proof: the service gives the notebook's answers
	$(PY) -m pytest tests/test_golden.py -v

test:
	$(PY) -m pytest -q

serve:   ## start the API on http://localhost:8000 (docs at /docs)
	$(PY) -m uvicorn fraud_service.entrypoints.api:app --port 8000

image:   ## build the container image
	docker build -t fraud-service:local .

smoke:   ## start the image and check it answers
	scripts/smoke_test.sh fraud-service:local
