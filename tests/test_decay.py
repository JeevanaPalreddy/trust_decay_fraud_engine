import pytest
from src.decay_engine import (
    calculate_decayed_score,
    calculate_outcome_delta,
    compute_updated_trust,
)


def test_decay_zero_elapsed_time():
    score = calculate_decayed_score(current_score=85.0, elapsed_hours=0.0)
    assert score == 85.0


def test_decay_towards_baseline_high_score():
    # 72 hours is 1 half-life. (80 - 50) * 0.5 + 50 = 65.0
    score = calculate_decayed_score(
        current_score=80.0, elapsed_hours=72.0, baseline_score=50.0, half_life_hours=72.0
    )
    assert pytest.approx(score, 0.1) == 65.0


def test_decay_towards_baseline_low_score():
    # 72 hours is 1 half-life. (20 - 50) * 0.5 + 50 = 35.0
    score = calculate_decayed_score(
        current_score=20.0, elapsed_hours=72.0, baseline_score=50.0, half_life_hours=72.0
    )
    assert pytest.approx(score, 0.1) == 35.0


def test_outcome_delta_success():
    delta = calculate_outcome_delta(status="SUCCESS", amount=100.0, current_score=50.0)
    assert delta > 0.0


def test_outcome_delta_chargeback():
    delta = calculate_outcome_delta(status="CHARGEBACK", amount=500.0, current_score=80.0)
    assert delta <= -25.0


def test_compute_updated_trust_pipeline():
    result = compute_updated_trust(
        current_score=90.0,
        elapsed_hours=72.0,  # Decays to 70.0
        status="SUCCESS",     # Adds positive delta
        amount=100.0,
        penalty_multiplier=5.0,  # Subtracts 5.0 penalty
    )

    assert result["initial_score"] == 90.0
    assert result["decayed_score"] < 90.0
    assert result["outcome_delta"] > 0.0
    assert result["graph_penalty"] == 5.0
    assert 0.0 <= result["final_score"] <= 100.0
