import random
import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.models import User
from src.score_service import process_transaction, advance_simulated_time


def generate_synthetic_stream(db: Session, num_events: int = 10, inject_fraud: bool = True) -> List[Dict[str, Any]]:
    """
    Generates a synthetic stream of transactions over simulated time.
    """
    users = db.query(User).all()
    if not users:
        return []

    logs = []

    statuses = ["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "SUSPICIOUS"]
    if inject_fraud:
        statuses.append("CHARGEBACK")

    for i in range(num_events):
        # Pick random user
        user = random.choice(users)
        status = random.choice(statuses)

        # Amount based on status
        if status == "CHARGEBACK":
            amount = round(random.uniform(500.0, 3000.0), 2)
        elif status == "SUSPICIOUS":
            amount = round(random.uniform(200.0, 1000.0), 2)
        else:
            amount = round(random.uniform(15.0, 350.0), 2)

        # Advance simulated time by 1 to 8 hours between transactions
        time_jump = round(random.uniform(1.0, 8.0), 1)
        advance_simulated_time(db, hours=time_jump)

        # Process transaction
        res = process_transaction(
            db=db,
            user_id=user.id,
            amount=amount,
            status=status,
            device_id=user.device_id,
            ip_address=user.ip_address,
        )
        res["simulated_time_jump_hours"] = time_jump
        logs.append(res)

    return logs


def inject_fraud_ring_attack(db: Session) -> Dict[str, Any]:
    """
    Creates a new synthetic user account linked to an existing fraudster via shared IP & Device,
    and executes an immediate high-value chargeback transaction.
    """
    charlie = db.query(User).filter(User.id == "usr_charlie").first()
    shared_device = charlie.device_id if charlie else "dev_ring_shared_x"
    shared_ip = charlie.ip_address if charlie else "10.0.0.99"

    new_id = f"usr_bot_{str(uuid.uuid4())[:6]}"
    new_user = User(
        id=new_id,
        name=f"Bot Account ({new_id})",
        email=f"{new_id}@fraudnet.cc",
        device_id=shared_device,
        ip_address=shared_ip,
        trust_score=50.0,
        baseline_trust=50.0,
    )
    db.add(new_user)
    db.commit()

    # Immediate fraudulent chargeback
    res = process_transaction(
        db=db,
        user_id=new_id,
        amount=1999.99,
        status="CHARGEBACK",
        device_id=shared_device,
        ip_address=shared_ip,
    )

    return {
        "attack_type": "FRAUD_RING_INJECTION",
        "created_user_id": new_id,
        "shared_device": shared_device,
        "shared_ip": shared_ip,
        "transaction_result": res,
    }
