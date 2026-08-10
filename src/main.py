from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db, init_db
from src.seed import seed_database
from src.models import User
from src.score_service import (
    process_transaction,
    get_user_score_details,
    advance_simulated_time,
)
from src.graph_engine import (
    detect_fraud_rings,
    get_fraud_ring_for_user,
    build_network_graph,
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Trust Score Decay & Fraud-Ring Detection API",
    description="Real-time trust scoring engine with exponential time decay and graph penalty propagation.",
    version="1.0.0",
    lifespan=lifespan,
)


# Pydantic Schemas
class TransactionRequest(BaseModel):
    user_id: str = Field(..., json_schema_extra={"example": "usr_alice"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 150.0})
    status: str = Field(..., json_schema_extra={"example": "SUCCESS"})  # SUCCESS, FAILED, CHARGEBACK, SUSPICIOUS
    device_id: Optional[str] = Field(None, json_schema_extra={"example": "dev_alice_01"})
    ip_address: Optional[str] = Field(None, json_schema_extra={"example": "192.168.1.10"})


class TimePassRequest(BaseModel):
    hours: float = Field(..., gt=0, json_schema_extra={"example": 24.0})



@app.get("/")
def read_root():
    return {
        "service": "Trust Scoring & Fraud Engine",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/score/{user_id}")
def get_score(user_id: str, db: Session = Depends(get_db)):
    """GET /score/{user_id}: Get calculated current decayed trust score, baseline, risk tier, and penalty."""
    try:
        details = get_user_score_details(db, user_id=user_id)
        return details
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/transaction")
def create_transaction(req: TransactionRequest, db: Session = Depends(get_db)):
    """POST /transaction: Process incoming transaction, apply decay + outcome delta + graph penalty."""
    try:
        result = process_transaction(
            db=db,
            user_id=req.user_id,
            amount=req.amount,
            status=req.status,
            device_id=req.device_id,
            ip_address=req.ip_address,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/fraud-ring/{user_id}")
def get_fraud_ring(user_id: str, db: Session = Depends(get_db)):
    """GET /fraud-ring/{user_id}: Get fraud-ring topology, connected accounts, and propagated penalty."""
    if user_id.lower() in ["all", "rings"]:
        rings = detect_fraud_rings(db)
        return {"count": len(rings), "rings": rings}

    ring_info = get_fraud_ring_for_user(db, user_id)
    if not ring_info.get("neighbors") and ring_info.get("trust_score") is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

    return ring_info


@app.post("/simulate/time-pass")
def simulate_time_pass(req: TimePassRequest, db: Session = Depends(get_db)):
    """POST /simulate/time-pass: Advances time by specified hours to simulate exponential decay across users."""
    res = advance_simulated_time(db, hours=req.hours)
    return res


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    """GET /users: List all users in system."""
    users = db.query(User).all()
    return [u.to_dict() for u in users]


@app.post("/seed")
def reseed_database():
    """POST /seed: Reset and reseed dummy database."""
    seed_database()
    return {"message": "Database successfully reseeded with baseline dummy users and network edges."}
