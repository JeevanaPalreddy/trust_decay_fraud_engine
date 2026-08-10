from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.models import User, Transaction, Connection
from src.decay_engine import compute_updated_trust, calculate_decayed_score
from src.graph_engine import get_fraud_penalty_for_user


def get_risk_tier(score: float) -> str:
    """Categorize score into risk tiers."""
    if score >= 80.0:
        return "LOW_RISK"
    elif score >= 60.0:
        return "MODERATE"
    elif score >= 40.0:
        return "ELEVATED"
    elif score >= 25.0:
        return "HIGH_RISK"
    else:
        return "CRITICAL"


def auto_detect_and_create_connections(
    db: Session, user: User, device_id: Optional[str], ip_address: Optional[str]
):
    """
    Automatically creates connection edges in DB if a user shares a device_id or ip_address with existing users.
    """
    now = datetime.now(timezone.utc)

    if device_id:
        # Find users with same device_id
        same_device_users = (
            db.query(User)
            .filter(User.device_id == device_id, User.id != user.id)
            .all()
        )
        for other in same_device_users:
            # Check existing connection
            existing = (
                db.query(Connection)
                .filter(
                    ((Connection.source_user_id == user.id) & (Connection.target_user_id == other.id))
                    | ((Connection.source_user_id == other.id) & (Connection.target_user_id == user.id)),
                    Connection.connection_type == "SHARED_DEVICE",
                )
                .first()
            )
            if not existing:
                conn = Connection(
                    source_user_id=user.id,
                    target_user_id=other.id,
                    connection_type="SHARED_DEVICE",
                    weight=0.9,
                    created_at=now,
                )
                db.add(conn)

    if ip_address:
        # Find users with same ip_address
        same_ip_users = (
            db.query(User)
            .filter(User.ip_address == ip_address, User.id != user.id)
            .all()
        )
        for other in same_ip_users:
            existing = (
                db.query(Connection)
                .filter(
                    ((Connection.source_user_id == user.id) & (Connection.target_user_id == other.id))
                    | ((Connection.source_user_id == other.id) & (Connection.target_user_id == user.id)),
                    Connection.connection_type == "SHARED_IP",
                )
                .first()
            )
            if not existing:
                conn = Connection(
                    source_user_id=user.id,
                    target_user_id=other.id,
                    connection_type="SHARED_IP",
                    weight=0.6,
                    created_at=now,
                )
                db.add(conn)

    db.commit()


def process_transaction(
    db: Session,
    user_id: str,
    amount: float,
    status: str,
    device_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1. Fetch user from DB.
    2. Auto-detect shared IP / Device connections.
    3. Calculate elapsed hours & exponential decay score.
    4. Compute graph-based fraud penalty propagation.
    5. Calculate transaction outcome delta.
    6. Update User's trust_score and last_updated_at in DB.
    7. Log Transaction record.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User '{user_id}' not found.")

    # Update user device/ip if provided
    if device_id:
        user.device_id = device_id
    if ip_address:
        user.ip_address = ip_address

    auto_detect_and_create_connections(db, user, user.device_id, user.ip_address)

    now = datetime.now(timezone.utc)
    # Make timezone aware comparison
    last_updated = user.last_updated_at
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - last_updated).total_seconds()
    elapsed_hours = max(0.0, elapsed_seconds / 3600.0)

    # Graph penalty propagation
    graph_penalty = get_fraud_penalty_for_user(db, user_id=user.id)

    # Compute updated score
    scoring_result = compute_updated_trust(
        current_score=user.trust_score,
        elapsed_hours=elapsed_hours,
        status=status,
        amount=amount,
        baseline_score=user.baseline_trust,
        penalty_multiplier=graph_penalty,
    )

    new_score = scoring_result["final_score"]
    user.trust_score = new_score
    user.last_updated_at = now

    # Record transaction
    txn = Transaction(
        user_id=user.id,
        amount=amount,
        status=status,
        device_id=user.device_id,
        ip_address=user.ip_address,
        applied_score=new_score,
        outcome_delta=scoring_result["outcome_delta"],
        timestamp=now,
    )
    db.add(txn)
    db.commit()

    verdict = "APPROVED"
    if new_score < 30.0 or status.upper() == "CHARGEBACK":
        verdict = "REJECTED"
    elif new_score < 50.0 or status.upper() == "SUSPICIOUS":
        verdict = "FLAGGED"

    return {
        "transaction_id": txn.id,
        "user_id": user.id,
        "user_name": user.name,
        "previous_score": scoring_result["initial_score"],
        "elapsed_hours": round(elapsed_hours, 2),
        "decayed_score": scoring_result["decayed_score"],
        "outcome_delta": scoring_result["outcome_delta"],
        "graph_penalty": scoring_result["graph_penalty"],
        "new_trust_score": new_score,
        "risk_tier": get_risk_tier(new_score),
        "verdict": verdict,
    }


def advance_simulated_time(db: Session, hours: float) -> Dict[str, Any]:
    """
    Simulates the passage of `hours` for all users in the system.
    Recalculates their decayed scores and pushes last_updated_at back into the past.
    """
    users = db.query(User).all()
    updated_users = []

    for user in users:
        # Push last_updated_at back by `hours` to simulate elapsed time
        if user.last_updated_at.tzinfo is None:
            user.last_updated_at = user.last_updated_at.replace(tzinfo=timezone.utc)
        
        user.last_updated_at = user.last_updated_at - timedelta(hours=hours)

        # Now compute decay
        now = datetime.now(timezone.utc)
        elapsed_hours = (now - user.last_updated_at).total_seconds() / 3600.0

        graph_penalty = get_fraud_penalty_for_user(db, user_id=user.id)
        decayed = calculate_decayed_score(
            current_score=user.trust_score,
            elapsed_hours=elapsed_hours,
            baseline_score=user.baseline_trust,
        )
        final_score = max(0.0, min(100.0, decayed - graph_penalty))

        old_score = user.trust_score
        user.trust_score = round(final_score, 2)
        user.last_updated_at = now

        updated_users.append({
            "user_id": user.id,
            "name": user.name,
            "old_score": old_score,
            "new_score": user.trust_score,
            "decay_delta": round(user.trust_score - old_score, 2),
        })

    db.commit()
    return {"elapsed_hours_added": hours, "users_updated": len(updated_users), "details": updated_users}


def get_user_score_details(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Returns user score details calculated up to the current moment.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User '{user_id}' not found.")

    now = datetime.now(timezone.utc)
    last_updated = user.last_updated_at
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)

    elapsed_hours = (now - last_updated).total_seconds() / 3600.0
    decayed_score = calculate_decayed_score(
        current_score=user.trust_score,
        elapsed_hours=elapsed_hours,
        baseline_score=user.baseline_trust,
    )
    graph_penalty = get_fraud_penalty_for_user(db, user_id=user.id)
    current_live_score = max(0.0, min(100.0, decayed_score - graph_penalty))

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "device_id": user.device_id,
        "ip_address": user.ip_address,
        "stored_score": user.trust_score,
        "current_live_score": round(current_live_score, 2),
        "baseline_trust": user.baseline_trust,
        "graph_penalty": round(graph_penalty, 2),
        "last_updated_at": user.last_updated_at.isoformat(),
        "elapsed_hours": round(elapsed_hours, 2),
        "risk_tier": get_risk_tier(current_live_score),
    }
