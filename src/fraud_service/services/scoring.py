"""Use case: score one payment, decide, and give the top reasons."""
from fraud_service.domain.assessment import Assessment, Reason
from fraud_service.domain.decision import Decision, decide
from fraud_service.domain.payment import Payment
from fraud_service.domain.ports import AlertSender, FraudModel


def what_if_typical(model: FraudModel, features: dict[str, float]) -> tuple[float, list[Reason]]:
    """Set each input alone to its typical value and re-score; the bigger the drop, the stronger
    the reason. Same method as the notebook. Returns the score and ALL reasons, strongest first."""
    variants = [dict(features)]  # row 0: the payment as it is
    for name in model.feature_names:
        variant = dict(features)
        variant[name] = model.typical_values[name]
        variants.append(variant)
    scores = model.score_many(variants)
    base, new_scores = scores[0], scores[1:]
    reasons = [
        Reason(feature=name, value=features[name], typical=model.typical_values[name], score_if_typical=s)
        for name, s in zip(model.feature_names, new_scores, strict=True)
    ]
    # Stable sort by drop, like pandas sort_values in the notebook
    reasons.sort(key=lambda r: base - r.score_if_typical, reverse=True)
    return base, reasons


class ScoringService:
    def __init__(self, model: FraudModel, block_threshold: float, top_reasons: int = 3,
                 alerts: AlertSender | None = None) -> None:
        self.model = model
        self.alerts = alerts
        self.block_threshold = block_threshold
        self.top_reasons = top_reasons

    def assess(self, payment: Payment) -> Assessment:
        score, reasons = what_if_typical(self.model, payment.features())
        decision = decide(score, self.model.review_threshold, self.block_threshold)
        if decision == Decision.BLOCK and self.alerts is not None:
            self.alerts.send_block_alert(score, self.model.version, reasons[0].feature)
        return Assessment(
            score=score,
            decision=decision,
            review_threshold=self.model.review_threshold,
            block_threshold=self.block_threshold,
            model_version=self.model.version,
            reasons=tuple(reasons[: self.top_reasons]),
        )
