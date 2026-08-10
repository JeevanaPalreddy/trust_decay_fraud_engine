from datetime import datetime, timedelta, timezone
from src.database import engine, Base, SessionLocal
from src.models import User, Transaction, Connection


def seed_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Create Users
        users_data = [
            {
                "id": "usr_alice",
                "name": "Alice Smith (Trusted)",
                "email": "alice@example.com",
                "device_id": "dev_alice_01",
                "ip_address": "192.168.1.10",
                "trust_score": 88.0,
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=2),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "usr_bob",
                "name": "Bob Johnson (Neutral)",
                "email": "bob@example.com",
                "device_id": "dev_bob_01",
                "ip_address": "192.168.1.20",
                "trust_score": 60.0,
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=5),
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "usr_charlie",
                "name": "Charlie Ring (Fraudster)",
                "email": "charlie_fraud@example.com",
                "device_id": "dev_ring_shared_x",
                "ip_address": "10.0.0.99",
                "trust_score": 15.0,  # Flagged / low trust
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=1),
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "usr_david",
                "name": "David Ring (Mule)",
                "email": "david_mule@example.com",
                "device_id": "dev_ring_shared_x",  # Shares device with Charlie!
                "ip_address": "10.0.0.100",
                "trust_score": 45.0,
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=12),
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "usr_eva",
                "name": "Eva Ring (Accomplice)",
                "email": "eva_acc@example.com",
                "device_id": "dev_eva_01",
                "ip_address": "10.0.0.99",  # Shares IP with Charlie!
                "trust_score": 52.0,
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=24),
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "usr_frank",
                "name": "Frank Connected",
                "email": "frank@example.com",
                "device_id": "dev_frank_01",
                "ip_address": "192.168.1.30",
                "trust_score": 75.0,
                "baseline_trust": 50.0,
                "last_updated_at": now - timedelta(hours=3),
                "created_at": now - timedelta(days=20),
            },
        ]

        users_dict = {}
        for u in users_data:
            user = User(**u)
            db.add(user)
            users_dict[u["id"]] = user

        db.commit()

        # 2. Create Explicit Connections (Graph Edges)
        connections_data = [
            # Fraud ring cluster edges
            {
                "source_user_id": "usr_charlie",
                "target_user_id": "usr_david",
                "connection_type": "SHARED_DEVICE",
                "weight": 0.9,
                "created_at": now - timedelta(days=7),
            },
            {
                "source_user_id": "usr_charlie",
                "target_user_id": "usr_eva",
                "connection_type": "SHARED_IP",
                "weight": 0.7,
                "created_at": now - timedelta(days=4),
            },
            {
                "source_user_id": "usr_david",
                "target_user_id": "usr_eva",
                "connection_type": "DIRECT_TRANSFER",
                "weight": 0.8,
                "created_at": now - timedelta(days=2),
            },
            # Legit cluster edges
            {
                "source_user_id": "usr_alice",
                "target_user_id": "usr_bob",
                "connection_type": "DIRECT_TRANSFER",
                "weight": 0.3,
                "created_at": now - timedelta(days=10),
            },
            {
                "source_user_id": "usr_bob",
                "target_user_id": "usr_frank",
                "connection_type": "SHARED_IP",
                "weight": 0.2,
                "created_at": now - timedelta(days=5),
            },
        ]

        for c in connections_data:
            conn = Connection(**c)
            db.add(conn)

        # 3. Create Sample Transactions
        transactions_data = [
            {
                "user_id": "usr_alice",
                "amount": 150.0,
                "status": "SUCCESS",
                "device_id": "dev_alice_01",
                "ip_address": "192.168.1.10",
                "applied_score": 85.0,
                "outcome_delta": 3.0,
                "timestamp": now - timedelta(hours=2),
            },
            {
                "user_id": "usr_charlie",
                "amount": 2500.0,
                "status": "CHARGEBACK",
                "device_id": "dev_ring_shared_x",
                "ip_address": "10.0.0.99",
                "applied_score": 40.0,
                "outcome_delta": -25.0,
                "timestamp": now - timedelta(hours=1),
            },
            {
                "user_id": "usr_david",
                "amount": 400.0,
                "status": "SUSPICIOUS",
                "device_id": "dev_ring_shared_x",
                "ip_address": "10.0.0.100",
                "applied_score": 50.0,
                "outcome_delta": -5.0,
                "timestamp": now - timedelta(hours=12),
            },
        ]

        for t in transactions_data:
            txn = Transaction(**t)
            db.add(txn)

        db.commit()
        print("Database seeded successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
