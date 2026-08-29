# FraudSpike AI architecture

## System boundary

```text
React + TypeScript frontend
          │
          │ same-origin /api requests
          ▼
FastAPI backend
  ├── detection and verification services
  ├── incident and investigation services
  ├── evaluation services
  ├── audit trail
  ├── SQLite now / PostgreSQL later
  └── backend-only LLM and Razorpay test-mode clients
```

The frontend is responsible for presentation, interaction, and chart
rendering. It must not call an LLM provider or Razorpay directly. The
backend is the only boundary allowed to access those services, and future AI
explanations must be generated from structured evidence assembled by the
backend.

## Frontend/backend communication

- The browser calls relative paths such as `/api/health` and future
  `/api/incidents` endpoints.
- Vite proxies `/api` to the local FastAPI service at `127.0.0.1:8000` during
  development.
- Replit serves the frontend on port `5000`; the backend listens on port
  `8000`.
- Production deployment should preserve the same relative API paths, either
  through a reverse proxy or a single backend process serving the built
  frontend.
- API contracts should be defined with typed Pydantic schemas in the backend
  and mirrored TypeScript types in the frontend as features are added.

## Core domain contracts

The shared contract layer currently defines:

- `PaymentEvent`: one payment event with a stable event reference, merchant,
  UTC timestamp, Decimal amount, payment attributes, privacy-safe customer and
  device references, coarse geography, optional fraud label, and extensible
  metadata.
- `FraudSpikeIncident`: a merchant-level detection result with its analysis
  window, baseline and observed rates, deviation, severity, lifecycle status,
  detector version, and optional confidence.
- `EvidenceItem`: structured evidence tied to an incident, including its
  metric, comparison value, supporting event references, time window, and
  confidence.
- `Investigation`: an incident investigation with hypotheses, evidence
  references, verification result, explanation, and defensive response.
- `EvaluationResult`: a versioned evaluation record whose counts and metrics
  are nullable until a real held-out evaluation has run.
- `AuditEvent`: a frozen, append-only-shaped record of defensive actions and
  their structured details.

### Payment event flow

Future ingestion will validate each incoming event as a `PaymentEvent`, store
it through the database boundary, and pass it to detection services. A
detector may create a `FraudSpikeIncident`; evidence and investigation
services then reference the original event IDs rather than copying sensitive
raw data. Verification, recommendations, and lifecycle transitions are
recorded as `AuditEvent` entries.

### Evaluation integrity

`EvaluationResult` deliberately leaves confusion counts, precision, recall,
F1, and false-positive cost empty until a versioned dataset has been scored
against a genuinely held-out test set. The contract accepts no invented
performance claims; an Evaluation Center must display only values produced by
the future evaluation service.

## Data and safety boundaries

- SQLite is the initial persistence target.
- SQLAlchemy is the database abstraction so PostgreSQL can be added later.
- No real payment credentials or payment results belong in the repository.
- Razorpay should remain test-mode-only until an explicit production decision.
- Detection and evaluation must use versioned datasets with a genuinely
  held-out test split.
- Evaluation output must be calculated from observed predictions; no metrics
  or cost values should be hard-coded.
- The system is defensive only: detection, verification, evidence
  correlation, auditability, and response recommendations.

## Recommended implementation order

1. Define payment-event, merchant, incident, evidence, and audit schemas.
2. Add SQLite persistence and deterministic seed/import tooling for
   explicitly labeled development data.
3. Implement a simple merchant-level baseline and the first FraudSpike
   detector behind a service interface.
4. Build held-out evaluation, confusion-matrix, precision/recall/F1, and
   false-positive-cost calculations before presenting metrics in the UI.
5. Add incident lifecycle APIs and the simulated/live event stream.
6. Add evidence correlation and verification/confidence rules.
7. Add the backend-only LLM investigation explanation with structured
   evidence as its sole input.
8. Add defensive response recommendations and the audit trail.
9. Add the command center and Evaluation Center views.
10. Add Razorpay Test Mode ingestion only where its test API provides useful,
    verifiable data for the selected workflow.