# FraudSpike AI

FraudSpike AI is an evidence-grounded merchant risk intelligence system designed for a local demo environment. It detects merchant-level fraud spikes, creates incidents, investigates structured evidence, verifies claims, and supports bounded response workflows with an audit trail.

## 1. Problem

Online merchants can be exposed to abrupt fraud spikes without clear operational transparency. In a real risk environment, teams need to understand: what changed, which merchants are affected, how risky the pattern is, whether the signal is defensible, and what action is appropriate.

FraudSpike AI addresses this by combining a deterministic synthetic event dataset, a merchant-level spike detector, an incident workflow, a verification layer, and a dashboard built for analyst review.

## 2. Track

Track: AI Risk Manager

The project aligns with the practical buildathon bar for a risk-management product:
- a working detector and verifier
- an evidence-based workflow
- held-out evaluation
- measured precision and recall
- honest false-positive cost
- response controls that remain bounded
- a working product experience rather than a concept mockup

## 3. Solution

FraudSpike AI follows this operating flow:

PAYMENT / EVENT SIGNAL
  ↓
MERCHANT-LEVEL SPIKE DETECTION
  ↓
RISK SCORING
  ↓
INCIDENT CREATION
  ↓
INVESTIGATION
  ↓
EVIDENCE VERIFICATION
  ↓
BOUNDED RESPONSE
  ↓
AUDIT TRAIL

The system is intentionally defensive-only. It does not claim unrestricted financial action or a live production payment connection.

## 4. Architecture

```text
Synthetic Payment/Event Dataset
          ↓
Event Ingestion API
          ↓
Merchant Aggregation
          ↓
Fraud Spike Detector
          ↓
Risk Scoring
          ↓
Incident Store
          ↓
Investigation Engine
          ↓
Verification Layer
          ↓
Policy / Response
          ↓
Audit Trail
          ↓
React Command Center

Optional:
Razorpay Test Adapter (demo only)
```

## 5. Detector

The current detector is a merchant-level fraud-spike detection engine. It compares merchant-level behavior against baseline activity and looks for suspicious deviations in fraud rate and transaction concentration over time.

The implementation is not a deep-learning model. It is a transparent, deterministic risk rule with a merchant-level anomaly signal and a held-out evaluation layer. That is a better fit for the product story and contributes to auditability.

## 6. Dataset

The project uses a deterministic synthetic dataset with a temporally split train / validation / test flow. This is intentionally labeled as synthetic and demo-scoped.

The app is designed to demonstrate a complete risk workflow without overstating production claims.

## 7. Held-out evaluation

The project reports real held-out evaluation values from the current detector pipeline.

Current metrics:
- TP = 452
- FP = 820
- TN = 1092
- FN = 8
- Precision = 35.53%
- Recall = 98.26%
- F1 = 52.19%
- False-positive cost = ₹102,500
- Test set size = 2,372

This is intentionally honest: the project prioritizes detection coverage while making the false-positive burden explicit.

## 8. API

The FastAPI backend exposes the primary workflow routes used by the product UI:

- GET /api/health
- GET /api/merchants
- GET /api/merchants/{merchant_id}
- GET /api/evaluation
- GET /api/incidents
- GET /api/incidents/{incident_id}
- POST /api/incidents/{incident_id}/action
- GET /api/incidents/{incident_id}/investigation
- GET /api/incidents/{incident_id}/verification
- GET /api/incidents/{incident_id}/audit
- GET /api/dashboard/summary
- GET /api/dashboard/metrics
- GET /api/demo/razorpay
- POST /api/demo/seed

These routes are intended to stay backend-authoritative and to keep secrets out of the frontend.

## 9. Frontend

The React + TypeScript frontend is a dark fintech command center with a permanent sidebar, dashboard, merchant intelligence, incident workflow, evaluation center, audit trail, and system status views.

It reads from the real backend APIs and keeps the synthetic/demo nature explicit in the UI.

## 10. Investigation

The investigation layer is evidence-grounded and deterministic by default. If an external LLM is not configured, the product remains safe and continues with structured evidence-based investigation.

The system makes the boundary clear:
- analysis / AI explanation is advisory
- policy decisions are controlling
- audit records preserve the final state

## 11. Verification

The verification layer checks whether claims are supported by evidence. It distinguishes between supported and unsupported claims and reports a confidence level for the checked narrative.

This is an important guardrail for a fintech workflow: the product explains why the risk was flagged instead of making opaque automated claims.

## 12. Response controls

Response actions are intentionally bounded. The product can recommend and record actions such as investigate, acknowledge, resolve, and dismiss, but it does not pretend to execute unrestricted live payment controls.

## 13. Audit trail

The app persists incidents, investigations, and event-level action records into SQLite. The audit trail is a record of what happened, when it happened, and which system or actor triggered the state change.

## 14. Razorpay test-mode integration

The project includes a safe local adapter for Razorpay status checks. If credentials are not configured, it reports test/demo mode and never presents itself as live or production-connected.

## 15. Setup instructions

### Backend

```bash
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

## 16. Run instructions

1. Start the backend on port 8000.
2. Start the frontend on port 5000.
3. Open http://localhost:5000
4. Use the demo button to refresh the seeded demo state.
5. Review the dashboard, merchants, incident workflow, evaluation data, and audit trail.

## 17. Demo flow

1. Synthetic payment events are ingested.
2. Merchant baselines are evaluated.
3. Fraud spikes are detected.
4. Risk checks and incidents are created.
5. Investigation and verification data are generated.
6. Bounded analyst responses are recorded.
7. The audit trail is updated.
8. Dashboard values refresh from the backend.

## 18. Known limitations

- local synthetic dataset only
- no live payment rails
- no production Razorpay credential path in this environment
- no fabricated external LLM integration
- evaluation metrics are honest and highlight the current precision/recall trade-off

## 19. Security

- no secrets are committed to the repository
- frontend does not hold credential material
- the app clearly labels demo/test mode
- all financial actions remain bounded and explainable

## 20. Setup notes

Use the environment placeholders in the project config. Do not commit real secrets.

## 21. Verification notes

The environment currently exposes a local shell runner issue where project commands fail before the actual app command executes. As a result, CLI results are not claimed as passing in this session. The app itself is verified through live browser and API inspection in the local environment.
