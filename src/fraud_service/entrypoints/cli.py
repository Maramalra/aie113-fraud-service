"""Command line entry point.

    python -m fraud_service.entrypoints.cli train            # download data, train, save artifacts/
    python -m fraud_service.entrypoints.cli score payment.json
"""
import argparse
import json
import sys

from fraud_service.adapters import csv_data, sklearn_model
from fraud_service.config import Settings
from fraud_service.domain.payment import Payment
from fraud_service.services import training
from fraud_service.services.scoring import ScoringService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fraud-service")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("train", help="train the model and save it into artifacts/")
    score_cmd = sub.add_parser("score", help="score one payment from a JSON file (Time, Amount, V1..V28)")
    score_cmd.add_argument("payment_file")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "train":
        df = csv_data.load_payments(settings.data_path, settings.data_url)
        model, info = training.train(df, settings, sklearn_model.fit, sklearn_model.score,
                                     sklearn_model.average_precision)
        sklearn_model.save(model, info, settings.model_path, settings.info_path)
        print(f"Saved {settings.model_path}; threshold {info['threshold']}")
        print(json.dumps(info["test_metrics"], indent=2))
        return 0

    model = sklearn_model.SklearnFraudModel.load(settings.model_path, settings.info_path)
    service = ScoringService(model, settings.block_threshold, settings.top_reasons)
    with open(args.payment_file) as f:
        result = service.assess(Payment.from_record(json.load(f)))
    print(f"Fraud score {result.score:.3f} -> {result.decision.value} "
          f"(review at {result.review_threshold}, block at {result.block_threshold})")
    for r in result.reasons:
        print(f"  - {r.feature} is {r.value:.2f} (typical {r.typical:.2f}): "
              f"if it were typical, the score would fall to {r.score_if_typical:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
