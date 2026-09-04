# RecoverAI

AI-powered failed payment recovery platform for Razorpay merchants. Ingests failed transactions, classifies failure causes with ML, predicts optimal retry strategy, auto-triggers recovery nudges, and provides a real-time analytics dashboard.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend    │◄───►│  FastAPI Backend  │◄───►│  SQLite          │
│  React+TS    │ WS  │  + WebSocket      │     │                  │
│  Vite        │     │  + local tasks    │     │  recoverai.db    │
└─────────────┘     └──────────────────┘     └─────────────────┘
                              │
                     ┌────────┴────────┐
                     │  ML Service      │
                     │  RandomForest +  │
                     │  GradientBoost   │
                     └──────────────────┘
                              │
                     ┌────────┴────────┐
                     │  In-memory events│
                     └──────────────────┘
```

## Quick Start (Local Only)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8000
```

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The backend API is available at http://localhost:8000.
The demo login is `demo@recoverai.com` / `demo1234`.

## Local Development (without Docker)

### Prerequisites
- Python 3.12+
- Node.js 20+
- SQLite (created automatically as `backend/recoverai.db`)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Demo Script

1. **Login** with demo credentials at http://localhost:5173
2. **Dashboard** — view recovery rate, failed payments, revenue recovered
3. **Simulate Live Traffic** — click the toggle to stream mock Razorpay events in real time via WebSocket
4. **Transactions** — expand any failed payment to see ML classification, recovery probability, and feature importances
5. **Retry** — click Retry on a failed transaction; a local background task simulates the outcome based on recovery probability
6. **Charts** — failure breakdown by reason, 30-day recovery trend

## ML Models

Two trained models (not rule-based):

| Model | Algorithm | Purpose |
|-------|-----------|---------|
| Failure Classifier | RandomForest (200 trees) | Predicts failure reason from transaction features |
| Recovery Predictor | GradientBoosting | Estimates probability a failed payment will convert on retry |

Features: amount, payment method, time of day, retry count, customer failure history, bank code, weekend/night flags.

Models saved to `ml/models/` via joblib. Retrain with:

```bash
python ml/train.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | JWT merchant login |
| POST | `/api/auth/register` | Register merchant |
| GET | `/api/transactions` | List transactions (filter/search/sort) |
| POST | `/api/transactions/{id}/predict` | Run ML inference |
| POST | `/api/transactions/{id}/retry` | Queue local background retry task |
| GET | `/api/dashboard/summary` | Aggregate KPIs |
| GET | `/api/dashboard/trend` | Recovery trend over time |
| GET | `/api/dashboard/failure-breakdown` | Failure reason distribution |
| WS | `/ws/live` | Real-time event stream |
| POST | `/api/simulation/live-feed` | Toggle live traffic simulation |

## Path to Production (Razorpay Integration)

The system is built webhook-ready. To connect live Razorpay:

1. **Configure webhooks** in Razorpay Dashboard → `payment.failed`, `payment.captured`
2. **Add webhook endpoint** — create `POST /api/webhooks/razorpay` that validates signature and inserts into `transactions` table (same schema as mock data)
3. **Set env vars** — `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
4. **Swap mock simulator** — disable the local live-feed task; real events arrive via webhooks
5. **Nudge delivery** — replace mock SMS/email sender in `retry_tasks.py` with Twilio/SendGrid/WhatsApp Business API
6. **Deploy** — Postgres + Redis + backend on any cloud; frontend on CDN

No schema or ML pipeline changes required — only the ingestion layer swaps from mock generator to webhook handler.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0 (async), SQLite, JWT auth
- **ML:** scikit-learn, XGBoost, pandas, joblib
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts, Framer Motion
- **Infra:** optional Docker files retained for later deployment; local development uses no containers

## License

MIT
