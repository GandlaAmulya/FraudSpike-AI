# FraudSpike AI

FraudSpike AI is a fraud-risk detection and risk-operations platform for merchant-level payment anomalies. It combines synthetic transaction ingestion, merchant risk scoring, incident management, verification, and a bounded analyst workflow in a local demo environment.

## Overview

The product is designed to detect suspicious merchant-level fraud spikes, explain why a signal is risky, and route the outcome into a structured investigation and response workflow without pretending to be a production payment system.

## Problem

Online merchants can experience abrupt fraud surges that are difficult to distinguish from normal variation. In a risk-ops setting, teams need clear evidence, explainable scoring, accountable workflow state, and defined boundaries on what action is appropriate.

## Key capabilities

- merchant-level fraud spike detection
- transaction risk scoring
- evidence-backed incident creation
- analyst investigation workflow
- claim verification against structured evidence
- stateful incident lifecycle with audit records
- bounded response actions for demo review
- held-out evaluation reporting with honest metrics

## Architecture

```text
Synthetic payment data
        ↓
FastAPI backend
        ↓
Risk scoring + detection
        ↓
Incident persistence
        ↓
Investigation + verification
        ↓
Response workflow + audit trail
        ↓
React frontend dashboard
```

## Data flow

1. Synthetic payment events are ingested or seeded.
2. The backend scores merchant activity and compares observed fraud behavior to the baseline.
3. Merchant spikes are surfaced as incidents.
4. Investigation and verification logic reviews supporting evidence.
5. Analysts can apply bounded response actions.
6. State changes are persisted and recorded in the audit trail.

## Fraud-spike detection

The detector is deterministic and rule-based rather than a production ML system. It evaluates merchant behavior against a baseline, identifies suspicious deviations in fraud rate and concentration, and assigns a risk-informed incident record.

## Transaction risk scoring

Risk scoring is intentionally simple, explainable, and bounded to the local demo environment. It uses merchant-level transaction patterns and evidence-backed heuristics to surface risk without claiming production-grade automated decisioning.

## Ingestion

The backend supports synthetic and structured event ingestion through API routes. The goal is to demonstrate a realistic fraud-risk pipeline while keeping the data scope clearly limited to local demo data.

## Incident management

Incidents are stored in the application database and follow explicit state transitions. Valid actions are limited to an allowed lifecycle, and invalid transitions are rejected with an audit-safe error. Each accepted change records the previous and new states.

## Investigation and verification

The investigation layer summarizes the supporting evidence and produces a bounded explanation for the detection. The verification layer checks whether the claims made by the investigation are actually supported by the observed evidence.

## Evaluation methodology

The project uses a held-out merchant-window evaluation workflow. The detector is evaluated only on the test split after the validation policy is selected, keeping the reported metric set consistent and leakage-safe.

## Verified metrics

Prediction unit: merchant_window
Test predictions: 96
TP: 21
FP: 8
TN: 66
FN: 1
Precision: 72.41%
Recall: 95.45%
F1: 82.35%

## Dataset

The project uses a deterministic synthetic payment dataset with a train/validation/test split. This keeps the demo realistic while remaining transparent about scope and limitations.

## Security

- secrets are not committed to the repository
- local environment variables remain in `.env` and `.env.example`
- no production payment credentials are required for the local demo
- all actioning remains bounded and explainable

## Razorpay demo/test-mode boundary

The Razorpay integration is intentionally demo-safe and test-mode aware. It does not claim live production connectivity or real payment execution.

## Limitations

- synthetic local dataset only
- no live payment rail access
- no production connector credentials
- no real-time streaming in the demo environment
- risk scoring is transparent and bounded by local rules rather than a production ML model

## Local setup

### Backend

```bash
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

## Testing

```bash
cd backend
pytest -q
```

```bash
cd frontend
npm run build
```

## Notes

FraudSpike AI is intended as a defensible local demo and competition project. It stays honest about the synthetic dataset, bounded workflow, and verified evaluation results.
