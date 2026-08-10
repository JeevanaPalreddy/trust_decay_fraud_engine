from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from src.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    device_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    trust_score = Column(Float, default=50.0, nullable=False)
    baseline_trust = Column(Float, default=50.0, nullable=False)
    last_updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "trust_score": round(self.trust_score, 2),
            "baseline_trust": round(self.baseline_trust, 2),
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(30), nullable=False)  # SUCCESS, FAILED, CHARGEBACK, SUSPICIOUS
    device_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    applied_score = Column(Float, nullable=False)
    outcome_delta = Column(Float, nullable=False, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "status": self.status,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
            "applied_score": round(self.applied_score, 2),
            "outcome_delta": round(self.outcome_delta, 2),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    target_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    connection_type = Column(String(50), nullable=False)  # SHARED_DEVICE, SHARED_IP, DIRECT_TRANSFER
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "source_user_id": self.source_user_id,
            "target_user_id": self.target_user_id,
            "connection_type": self.connection_type,
            "weight": self.weight,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
