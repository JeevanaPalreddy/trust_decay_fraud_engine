# Trust Score Decay & Fraud-Ring Detection Engine

A demo risk platform that combines **time-decaying trust scores** with **graph-based fraud-ring detection**.  
It scores users from transaction outcomes, lets idle scores drift back toward a neutral baseline, and propagates risk across accounts linked by shared devices, IPs, or transfers.

Built with **FastAPI**, **Streamlit**, **SQLAlchemy (SQLite)**, and **NetworkX**.

---

## Features

- **Exponential trust decay** toward a baseline (default half-life: 72 hours)
- **Outcome-based score updates** for `SUCCESS`, `FAILED`, `SUSPICIOUS`, and `CHARGEBACK`
- **Auto-linking** of accounts that share a device ID or IP address
- **Fraud-ring detection** via connected components in a user network graph
- **Penalty propagation** from flagged fraud nodes to nearby accounts (distance-weighted)
- **REST API** for scoring, transactions, rings, and time simulation
- **Streamlit dashboard** for risk tables, decay curves, graph visualization, and attack simulation
- **Seeded demo world** with trusted users and a pre-built fraud cluster

---

## Architecture

```text
Streamlit UI  ─┐
FastAPI REST  ─┼─► score_service ─┬─► decay_engine (math)
pytest        ─┘                  └─► graph_engine (NetworkX)
                                        │
                                        ▼
                              SQLite (trust_engine.db)
```

| Module | Role |
|--------|------|
| `src/decay_engine.py` | Decay formula + transaction outcome deltas |
| `src/graph_engine.py` | Network graph, ring detection, penalty propagation |
| `src/score_service.py` | Orchestrates txn processing, live scores, time jumps |
| `src/main.py` | FastAPI endpoints |
| `src/dashboard.py` | Streamlit ops console |
| `src/seed.py` | Reset + load demo users/edges/transactions |
| `src/simulator.py` | Synthetic txn streams + fraud-ring attack injection |

---

## How scoring works

### 1. Time decay

\[
S(t) = S_{baseline} + (S_{current} - S_{baseline}) \cdot e^{-\lambda t}
\quad\text{where}\quad
\lambda = \frac{\ln 2}{\text{half\_life}}
\]

Default baseline is `50.0`. After one half-life of inactivity, the gap to baseline is cut in half.

### 2. Transaction deltas

| Status | Effect |
|--------|--------|
| `SUCCESS` | Positive boost (diminishes near score 100) |
| `CHARGEBACK` | Heavy penalty (~-25 to -40) |
| `SUSPICIOUS` | Moderate penalty (~-12) |
| `FAILED` | Mild penalty (~-3) |

### 3. Graph penalty

Users with `trust_score < 30` are treated as fraud nodes. Nearby accounts receive:

\[
penalty += \frac{(100 - fraud\_score) \times 0.2}{distance^2}
\]

(capped at 50). Final score is clamped to `[0, 100]`.

### 4. Verdicts

| Condition | Verdict |
|-----------|---------|
| Score `< 30` or status `CHARGEBACK` | `REJECTED` |
| Score `< 50` or status `SUSPICIOUS` | `FLAGGED` |
| Otherwise | `APPROVED` |

### Risk tiers

`LOW_RISK` (≥80) → `MODERATE` (≥60) → `ELEVATED` (≥40) → `HIGH_RISK` (≥25) → `CRITICAL` (<25)

---

## Demo seed data

| User | Role | Notes |
|------|------|--------|
| `usr_alice` | Trusted | High score, clean device/IP |
| `usr_bob` | Neutral | Linked lightly to Alice/Frank |
| `usr_frank` | Trusted-ish | Shared-IP edge with Bob |
| `usr_charlie` | Fraudster | Low score (~15), ring center |
| `usr_david` | Mule | Shares Charlie’s **device** |
| `usr_eva` | Accomplice | Shares Charlie’s **IP** |

Charlie → David → Eva form the initial fraud ring.

---

## Quick start

### Prerequisites

- Python 3.10+
- `pip`

### Setup

```bash
cd trust_decay_fraud_engiine

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m src.seed
```

### Run the dashboard (recommended)

```bash
PYTHONPATH=. streamlit run src/dashboard.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

### Run the API

```bash
uvicorn src.main:app --reload --port 8000
```

Interactive docs: http://127.0.0.1:8000/docs

### Run tests

```bash
pytest -v
```

---

## Using the dashboard

**Sidebar**

- **Reseed Database** — wipe and reload demo data
- **+12 Hours / +7 Days** — fast-forward decay
- **Inject Fraud Ring Attack** — spawn a bot sharing Charlie’s device/IP + chargeback

**Tabs**

1. **System Overview** — live scores, risk tiers, recent transactions  
2. **Time Decay Inspector** — interactive decay curve (half-life / baseline / penalty)  
3. **Fraud-Ring Graph** — NetworkX visualization + ring details  
4. **Simulator** — submit custom transactions or generate a synthetic stream  

### Suggested first walkthrough

1. Click **Reseed Database**
2. Compare Alice (high trust) vs Charlie (critical) on Overview
3. Open the Graph tab and inspect the Charlie–David–Eva ring
4. Submit a `SUCCESS` for Alice and a `CHARGEBACK` for Charlie
5. Inject a fraud-ring attack and watch the graph grow
6. Fast-forward **+7 Days** to see scores drift toward baseline

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health / service info |
| `GET` | `/users` | List all users |
| `GET` | `/score/{user_id}` | Live decayed score + tier + graph penalty |
| `POST` | `/transaction` | Process a transaction end-to-end |
| `GET` | `/fraud-ring/{user_id}` | Neighbors + ring membership for a user |
| `GET` | `/fraud-ring/all` | All detected fraud rings |
| `POST` | `/simulate/time-pass` | Advance simulated time by `hours` |
| `POST` | `/seed` | Reset and reseed the database |

### Example requests

```bash
# Live score
curl http://127.0.0.1:8000/score/usr_alice

# Process a successful payment
curl -X POST http://127.0.0.1:8000/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_alice",
    "amount": 150.0,
    "status": "SUCCESS",
    "device_id": "dev_alice_01",
    "ip_address": "192.168.1.10"
  }'

# Inspect Charlie's fraud ring
curl http://127.0.0.1:8000/fraud-ring/usr_charlie

# Simulate 24 hours of decay
curl -X POST http://127.0.0.1:8000/simulate/time-pass \
  -H "Content-Type: application/json" \
  -d '{"hours": 24}'
```

### Transaction body

```json
{
  "user_id": "usr_alice",
  "amount": 150.0,
  "status": "SUCCESS",
  "device_id": "dev_alice_01",
  "ip_address": "192.168.1.10"
}
```

`status` must be one of: `SUCCESS`, `FAILED`, `SUSPICIOUS`, `CHARGEBACK`.

---

## Project structure

```text
trust_decay_fraud_engiine/
├── README.md
├── requirements.txt
├── src/
│   ├── main.py            # FastAPI app
│   ├── dashboard.py       # Streamlit UI
│   ├── database.py        # SQLite engine / sessions
│   ├── models.py          # User, Transaction, Connection
│   ├── decay_engine.py    # Decay + outcome math
│   ├── graph_engine.py    # Rings + penalty propagation
│   ├── score_service.py   # Scoring orchestration
│   ├── seed.py            # Demo data loader
│   └── simulator.py       # Synthetic attacks / streams
└── tests/
    ├── test_api.py
    └── test_decay.py
```

The SQLite file `trust_engine.db` is created locally at runtime (gitignored). Override path with the `DB_PATH` environment variable if needed.

---

## Dependencies

See `requirements.txt`:

- `fastapi`, `uvicorn`, `pydantic`
- `sqlalchemy`
- `networkx`
- `streamlit`, `plotly`
- `pytest`, `httpx`

---

## Notes

- This is a **learning / demo** system, not a production fraud platform.
- No authentication, rate limiting, or hardened identity signals are included.
- Graph penalty and verdict thresholds are intentional heuristics for clarity.

---

## License

MIT (or your preferred license).
