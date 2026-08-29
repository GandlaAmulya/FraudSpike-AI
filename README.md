# FraudSpike AI

Foundational monorepo scaffold for **FraudSpike AI — Autonomous Payment
Fraud-Spike Detection & Investigation Agent**.

This repository intentionally contains architecture and configuration only.
The detector, dashboard, investigation agent, evaluation metrics, and Razorpay
integration are not implemented yet.

## Repository layout

```text
.
├── backend/                 # FastAPI service and domain boundaries
│   ├── app/
│   │   ├── api/             # HTTP routes and request handling
│   │   ├── core/            # Settings and cross-cutting configuration
│   │   ├── db/              # Database engine/session boundary
│   │   ├── detectors/       # Future fraud-spike detection engine
│   │   ├── evaluation/      # Future held-out evaluation workflows
│   │   ├── incidents/       # Future incident lifecycle operations
│   │   ├── integrations/    # Future defensive external integrations
│   │   ├── investigation/   # Future evidence and AI investigation flows
│   │   ├── models/          # Future SQLAlchemy models
│   │   ├── schemas/         # Future API request/response schemas
│   │   └── services/        # Future application services
│   └── tests/               # Backend tests
├── docs/                    # Architecture and implementation notes
└── frontend/                # React + TypeScript + Vite client
    └── src/
        ├── components/      # Future reusable interface components
        ├── features/        # Future product feature areas
        ├── lib/             # Client utilities and API boundary
        └── pages/           # Future route-level views
```

## Local development

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend is configured for Replit on `0.0.0.0:5000`. API requests should
use relative `/api/...` paths so the same client works behind the Replit
proxy and in deployment.

### Backend

```bash
cd backend
python -m venv .venv  # local machines only; do not use this for Replit
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend exposes only `GET /api/health` at this stage. It defaults to a
SQLite URL and keeps the database access behind SQLAlchemy so PostgreSQL can
be introduced later without changing feature code.

See [docs/architecture.md](docs/architecture.md) for the communication
contract and recommended implementation order.