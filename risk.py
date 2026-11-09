from typing import Literal

LOW_RISK_UPPER_BOUND = 0.3
HIGH_RISK_LOWER_BOUND = 0.6


def classify_risk(score: float) -> Literal["low", "medium", "high"]:
    if not 0 <= score <= 1:
        raise ValueError("Risk score must be between 0 and 1")
    if score < LOW_RISK_UPPER_BOUND:
        return "low"
    if score < HIGH_RISK_LOWER_BOUND:
        return "medium"
    return "high"
