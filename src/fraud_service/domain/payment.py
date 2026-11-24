"""A card payment, and how it becomes the model's inputs."""
from dataclasses import dataclass

V_NAMES = tuple(f"V{i}" for i in range(1, 29))
# The model's inputs, in the exact order it was trained on.
FEATURE_NAMES = V_NAMES + ("Amount", "hour")


@dataclass(frozen=True)
class Payment:
    """One card payment as it arrives: seconds since the data's start, amount, V1..V28."""

    time: float
    amount: float
    v: tuple[float, ...]  # V1..V28, in order

    def __post_init__(self) -> None:
        if len(self.v) != 28:
            raise ValueError("a payment needs exactly 28 V values (V1 to V28)")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        if self.time < 0:
            raise ValueError("time cannot be negative")

    @property
    def hour(self) -> float:
        """Hour of the day (0-23), assuming the data starts at midnight, as in the notebook."""
        return (self.time // 3600) % 24

    def features(self) -> dict[str, float]:
        """The model's inputs, built exactly as in training."""
        values = dict(zip(V_NAMES, self.v, strict=True))
        values["Amount"] = self.amount
        values["hour"] = self.hour
        return {name: values[name] for name in FEATURE_NAMES}

    @classmethod
    def from_record(cls, record: dict[str, float]) -> "Payment":
        """Build from the dataset's column names: Time, Amount, V1..V28."""
        return cls(
            time=float(record["Time"]),
            amount=float(record["Amount"]),
            v=tuple(float(record[name]) for name in V_NAMES),
        )
