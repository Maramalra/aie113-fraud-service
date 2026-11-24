# ---- Stage 1: builder — install libraries, download data, train the model -------------------
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 OMP_NUM_THREADS=1

# Libraries into their own folder (a virtual environment) we can copy as one piece.
# Copied before the code, so a code change does not reinstall them (layer cache).
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# The data (150 MB) in its own layer: downloaded once, reused on rebuilds. It stays in this stage only.
ARG DATA_URL=https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv
RUN python -c "import urllib.request,sys; urllib.request.urlretrieve(sys.argv[1], 'creditcard.csv')" "$DATA_URL"

# Train with our own code: same steps and numbers as the notebook (~5 s).
COPY pyproject.toml .
COPY src ./src
RUN /opt/venv/bin/pip install --no-deps . \
 && FRAUD_DATA_PATH=creditcard.csv FRAUD_MODEL_PATH=artifacts/fraud_model.joblib \
    FRAUD_INFO_PATH=artifacts/model_info.json /opt/venv/bin/python -m fraud_service.entrypoints.cli train

# ---- Stage 2: runtime — only what the service needs ------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 PATH=/opt/venv/bin:$PATH \
    FRAUD_MODEL_PATH=/app/artifacts/fraud_model.joblib FRAUD_INFO_PATH=/app/artifacts/model_info.json

# A normal user: if someone broke in through the service, they would not be root.
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /build/artifacts ./artifacts
USER app

EXPOSE 8000
# Docker asks "are you ready?" every 15 s using our readiness endpoint.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"
CMD ["uvicorn", "fraud_service.entrypoints.api:app", "--host", "0.0.0.0", "--port", "8000"]
