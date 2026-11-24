"""Web entry point (FastAPI). Start with:  make serve   then open http://localhost:8000/docs"""
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from fraud_service.adapters import log_masking
from fraud_service.adapters.alerts import NoAlerts, WebhookAlertSender
from fraud_service.config import Settings
from fraud_service.domain.payment import V_NAMES, Payment
from fraud_service.services.scoring import ScoringService

log = logging.getLogger("fraud_service.api")


# ---- The contract -----------------------------------------------------------------------------
class PaymentIn(BaseModel):
    """One card payment, with the dataset's field names."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, json_schema_extra={"example": {
        "Time": 154278.0, "Amount": 1504.93, **{n: 0.0 for n in V_NAMES}}})

    Time: float = Field(ge=0, description="seconds since the start of the data (gives the hour of day)")
    Amount: float = Field(ge=0, le=1_000_000, description="amount paid")
    # V1..V28: anonymous numbers from the bank's privacy transformation
    V1: float; V2: float; V3: float; V4: float; V5: float; V6: float; V7: float
    V8: float; V9: float; V10: float; V11: float; V12: float; V13: float; V14: float
    V15: float; V16: float; V17: float; V18: float; V19: float; V20: float; V21: float
    V22: float; V23: float; V24: float; V25: float; V26: float; V27: float; V28: float


class ReasonOut(BaseModel):
    feature: str
    value: float
    typical: float
    score_if_typical: float = Field(description="the score if this input alone were typical")


class AssessmentOut(BaseModel):
    score: float = Field(description="fraud score 0..1: a ranking, not an exact probability")
    decision: Literal["allow", "review", "block"]
    review_threshold: float
    block_threshold: float
    model_version: str
    reasons: list[ReasonOut]
    note: str = "Teaching model trained on 2013 data. A human must check before acting on a payment."


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict] = []


class ErrorOut(BaseModel):
    error: ErrorBody


def error(status: int, code: str, message: str, details: list[dict] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
                                                               "details": details or []}})


def make_alert_sender(settings: Settings):
    if settings.alert_webhook_url and settings.alert_webhook_token:
        return WebhookAlertSender(settings.alert_webhook_url, settings.alert_webhook_token)
    return NoAlerts()


# ---- The app ----------------------------------------------------------------------------------
def create_app(settings: Settings | None = None, model=None) -> FastAPI:
    """`model` can be passed in (tests use a fake); otherwise the real one is loaded at start-up."""
    settings = settings or Settings()
    token = settings.alert_webhook_token
    log_masking.install([token.get_secret_value()] if token else [])
    # What the service runs with. SecretStr prints as '**********', never the real token.
    log.info("settings_effective %s", settings.model_dump(exclude={"thresholds_to_try"}))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = None
        try:
            m = model
            if m is None:
                from fraud_service.adapters.sklearn_model import SklearnFraudModel
                m = SklearnFraudModel.load(settings.model_path, settings.info_path)
            app.state.service = ScoringService(m, settings.block_threshold, settings.top_reasons,
                                               alerts=make_alert_sender(settings))
            log.info("model loaded: version %s", m.version)
        except Exception as exc:  # stay alive but not ready, so the problem is visible
            log.error("model could not be loaded: %s", type(exc).__name__)
        yield

    app = FastAPI(title="Fraud scoring service", version="1.0.0", lifespan=lifespan,
                  description="Scores one card payment, decides allow/review/block, and gives the top reasons.")

    @app.exception_handler(RequestValidationError)
    async def bad_request(_: Request, exc: RequestValidationError):
        # Say WHICH field and WHAT is wrong, but never echo the values sent (private payment data).
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "problem": e["msg"]}
                   for e in exc.errors()]
        return error(422, "invalid_payment", "The payment is missing fields or has invalid values.", details)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("unexpected error")
        return error(500, "internal_error", "Something went wrong on our side.")

    @app.get("/health/live", tags=["health"])
    def live():
        """Is the process running?"""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"], responses={503: {"model": ErrorOut}})
    def ready(request: Request):
        """Is the model loaded and able to score?"""
        service = request.app.state.service
        if service is None:
            return error(503, "not_ready", "The model is not loaded.")
        return {"status": "ready", "model_version": service.model.version}

    @app.post("/v1/score", response_model=AssessmentOut, tags=["fraud"],
              responses={422: {"model": ErrorOut}, 503: {"model": ErrorOut}})
    def score(payment: PaymentIn, request: Request):  # plain def: scikit-learn work runs in a thread
        """Score one payment: fraud score, decision and the top reasons."""
        service: ScoringService | None = request.app.state.service
        if service is None:
            return error(503, "not_ready", "The model is not loaded.")
        try:
            domain_payment = Payment.from_record(payment.model_dump())
        except ValueError as exc:
            return error(422, "invalid_payment", str(exc))
        result = service.assess(domain_payment)
        return AssessmentOut(
            score=result.score, decision=result.decision.value,
            review_threshold=result.review_threshold, block_threshold=result.block_threshold,
            model_version=result.model_version,
            reasons=[ReasonOut(feature=r.feature, value=r.value, typical=r.typical,
                               score_if_typical=r.score_if_typical) for r in result.reasons],
        )

    return app


app = create_app()
