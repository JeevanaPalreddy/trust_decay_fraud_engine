import math
from typing import Dict, Any


def calculate_decayed_score(
    current_score: float,
    elapsed_hours: float,
    baseline_score: float = 50.0,
    half_life_hours: float = 72.0,
    min_score: float = 0.0,
    max_score: float = 100.0,
) -> float:
    """
    Calculates the exponential decay of a trust score over elapsed time.
    Formula: S(t) = S_baseline + (S_current - S_baseline) * exp(-lambda * t)
    where lambda = ln(2) / half_life_hours.
    """
    if elapsed_hours <= 0:
        return max(min_score, min(max_score, current_score))

    decay_constant = math.log(2) / half_life_hours
    decayed = baseline_score + (current_score - baseline_score) * math.exp(-decay_constant * elapsed_hours)
    
    return max(min_score, min(max_score, round(decayed, 4)))


def calculate_outcome_delta(
    status: str,
    amount: float = 0.0,
    current_score: float = 50.0,
) -> float:
    """
    Calculates the score adjustment (delta) based on a transaction outcome.
    - SUCCESS: positive boost with diminishing returns as current_score approaches 100.
    - CHARGEBACK: heavy negative penalty (-25 to -40 based on amount).
    - SUSPICIOUS: moderate penalty (-10 to -20).
    - FAILED: minor penalty (-3 to -5).
    """
    status_upper = status.upper()

    if status_upper == "SUCCESS":
        # Base boost of +5.0, diminished as score approaches max (100)
        diminish_factor = max(0.1, (100.0 - current_score) / 50.0)
        # Larger valid transactions give slightly higher boost
        amount_factor = min(2.0, 1.0 + math.log10(max(1.0, amount / 50.0)))
        delta = 4.0 * diminish_factor * amount_factor
        return round(min(15.0, delta), 2)

    elif status_upper == "CHARGEBACK":
        # Severe penalty
        amount_penalty = min(15.0, math.log10(max(1.0, amount / 10.0)) * 5.0)
        return round(-(25.0 + amount_penalty), 2)

    elif status_upper == "SUSPICIOUS":
        return round(-12.0, 2)

    elif status_upper == "FAILED":
        return -3.0

    return 0.0


def compute_updated_trust(
    current_score: float,
    elapsed_hours: float,
    status: str = None,
    amount: float = 0.0,
    baseline_score: float = 50.0,
    half_life_hours: float = 72.0,
    penalty_multiplier: float = 0.0,
) -> Dict[str, Any]:
    """
    Full pipeline:
    1. Apply exponential time decay since last update.
    2. Apply transaction outcome delta (if transaction occurs).
    3. Apply graph-based fraud penalty if penalty_multiplier > 0.
    4. Clamp score between 0.0 and 100.0.
    """
    # 1. Exponential decay
    decayed_score = calculate_decayed_score(
        current_score=current_score,
        elapsed_hours=elapsed_hours,
        baseline_score=baseline_score,
        half_life_hours=half_life_hours,
    )

    # 2. Outcome delta
    delta = 0.0
    if status:
        delta = calculate_outcome_delta(status, amount, current_score=decayed_score)

    # 3. Fraud penalty propagation deduction
    graph_penalty = round(penalty_multiplier, 2)

    # 4. Net score
    net_score = max(0.0, min(100.0, decayed_score + delta - graph_penalty))

    return {
        "initial_score": current_score,
        "elapsed_hours": elapsed_hours,
        "decayed_score": round(decayed_score, 2),
        "outcome_delta": delta,
        "graph_penalty": graph_penalty,
        "final_score": round(net_score, 2),
    }
