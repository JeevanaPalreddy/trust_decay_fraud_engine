import os
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.seed import seed_database

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    seed_database()


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "running"


def test_list_users():
    res = client.get("/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 5


def test_get_score():
    res = client.get("/score/usr_alice")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "usr_alice"
    assert "current_live_score" in data
    assert data["risk_tier"] in ["LOW_RISK", "MODERATE", "ELEVATED", "HIGH_RISK", "CRITICAL"]


def test_process_transaction():
    payload = {
        "user_id": "usr_alice",
        "amount": 200.0,
        "status": "SUCCESS",
        "device_id": "dev_alice_01",
        "ip_address": "192.168.1.10",
    }
    res = client.post("/transaction", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] in ["APPROVED", "FLAGGED", "REJECTED"]
    assert data["new_trust_score"] > 0


def test_fraud_ring_endpoint():
    res = client.get("/fraud-ring/usr_charlie")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "usr_charlie"
    assert data["in_fraud_ring"] is True


def test_time_pass_simulation():
    res = client.post("/simulate/time-pass", json={"hours": 48.0})
    assert res.status_code == 200
    data = res.json()
    assert data["elapsed_hours_added"] == 48.0
