# FraudSpike AI

FraudSpike AI is a merchant fraud-risk investigation platform built to surface suspicious behavior, connect it to structured evidence, and support analyst review in a transparent, auditable workflow. The project is designed as a local demo system for fraud detection and investigation, with clear boundaries around what is evidence-backed, what is rule-based, and what remains a human decision.

## Problem statement

Payment fraud operations teams need to identify abnormal merchant activity quickly, explain why a signal is suspicious, and escalate only when the evidence is strong enough to justify a review. In real fraud programs, this requires more than a single score: it requires good signals, trusted evidence, a review workflow, and a complete audit trail.

FraudSpike AI models this challenge in a compact, local environment using synthetic payment data so the detection pipeline, investigation process, and decision logic remain explainable and demonstrable.

## Solution overview

This project combines:

- deterministic fraud-spike detection for merchant-level anomalies
- transaction risk scoring based on structured evidence
- persisted incident records and lifecycle transitions
- evidence-backed investigation summaries
- local anomaly analysis as a supplemental, transparent signal
- analyst-facing review flows with recommendations and audit logging
- honest held-out evaluation reporting based on a real validation/test split

The system is intentionally designed to be transparent about the difference between:

- rule-based fraud detection
- local anomaly analysis
- analyst decisioning
- constrained demo operations

## Architecture

```text
Synthetic payment events
        │
        ▼
FastAPI backend
        │
        ├─ risk scoring
        ├─ merchant spike detection
        ├─ SQLite incident persistence
        ├─ evidence assembly
        ├─ investigation + verification
        └─ audit trail
        │
        ▼
React + TypeScript frontend
        │
        ├─ dashboard
        ├─ incident review
        ├─ investigation workstation
        ├─ audit and evaluation views
        └─ analyst workflow
```

## Core capabilities

- merchant-level fraud spike detection from payment history patterns
- transaction-level risk scoring for suspicious event behavior
- incident creation with severity, lifecycle, and evidence references
- evidence-grounded investigation summaries that tie conclusions to stored records
- local anomaly analysis using a lightweight Isolation Forest signal when enough history exists
- human-in-the-loop analyst review with persisted lifecycle transitions
- persistence and audit records that make the workflow explainable and traceable
- held-out evaluation with transparent metric calculation and honest reporting

## Investigation flow

1. Payment events are ingested or seeded into the local system.
2. Risk scoring evaluates individual transactions and event clusters.
3. A merchant-level spike detector identifies abnormal fraud-rate deviations.
4. An incident is created with the observed rate, baseline rate, severity, and evidence window.
5. The investigation layer assembles supporting evidence and produces a bounded explanation.
6. A local anomaly signal is calculated only when enough transaction history exists.
7. The analyst reviews the recommendation, records a decision, and the state is audited.

## Evidence-grounded AI explanation

The project does not claim that the system makes autonomous payment decisions.

Instead, it takes a grounded approach:

- findings are tied to real persisted evidence
- investigations explain what changed and why it matters
- local anomaly scoring is presented as a supplementary signal
- unsupported claims are not treated as verified conclusions
- the UI and API are explicit about where evidence is insufficient

This makes the platform far more credible in a competition or demo setting than a generic chatbot-style fraud demo.

## Local ML anomaly component

The local anomaly component is intentionally narrow and honest:

- it is a supporting signal for investigation, not the core decision engine
- it uses persisted event features such as amount, amount ratio, velocity, device reuse, and temporal patterns
- it only runs when enough transaction history exists
- if evidence is insufficient, the system returns a clear insufficient-evidence state instead of fabricating certainty

The deterministic fraud detection and risk engine remain the primary operational logic. The local anomaly model does not replace them.

## Human-in-the-loop decision model

Analyst actions are recorded, not executed automatically. The system supports a review-oriented decision flow such as:

- INVESTIGATE
- VERIFY
- HOLD

These actions are recorded against the investigation and incident for traceability. The system does not perform destructive payment actions in the demo workflow.

## Auditability

Every meaningful workflow change is stored with an audit record containing:

- incident ID
- investigation reference when relevant
- action taken
- source or system origin
- timestamp
- structured details

This supports investigation traceability and keeps the demo operational flow credible and reviewable.

## Backend setup

```bash
cd backend
python -m pip install -e .
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

## How to run

From the project root:

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5000
```

Then open the frontend in the browser. Start the `FRAUD SPIKE` scenario from
Live Stream to ingest events through the real risk engine. The resulting
persisted incidents can be opened from Incident Center, where investigation,
local ML assessment, evidence references, and audit events are available.

## API overview

The backend exposes a set of demo-oriented API routes for:

- health checks
- synthetic event ingestion
- transaction risk scoring
- merchant and incident discovery
- investigation generation
- verification and audit queries
- evaluation reporting

Core investigation routes include:

```http
POST /api/incidents/{incident_id}/investigate
GET /api/incidents/{incident_id}/investigation
GET /api/incidents/{incident_id}/audit
GET /api/incidents/{incident_id}/verification
```

## Testing

```bash
cd backend
pytest -q
```

```bash
cd frontend
npm.cmd run build
```

## Production limitations and scope

FraudSpike AI is a local demonstration platform and not a production payment processor. It is intentionally scoped to:

- synthetic demo data
- local persistence
- explainable investigation logic
- transparent, bounded decision support
- human review as the final step

The project does not claim real-time production monitoring, live payment execution, or externally connected fraud infrastructure.

## Summary

FraudSpike AI reflects a practical fraud-operations workflow: detect suspicious merchant behavior, investigate structured evidence, explain the risk, keep the workflow auditable, and leave the final decision with the analyst. The result is a credible local demo platform that is clear about its scope and technically honest about what it does and does not do.
