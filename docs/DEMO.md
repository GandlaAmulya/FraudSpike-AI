# FraudSpike AI demo guide

## Demo goal

This demo is designed to show how a fraud operations team can move from a suspicious merchant signal to a reviewable investigation workflow without claiming production-grade automation.

## What the demo shows

- merchant-level fraud spike detection
- risk scoring on merchant payment behavior
- incident creation and lifecycle management
- evidence-backed investigation summaries
- review of supported vs unsupported claims
- local anomaly support as an optional, secondary signal
- analyst decision recording and audit trail persistence

## Recommended flow

1. Launch the backend and frontend.
2. Open the dashboard and inspect the current metrics.
3. Select a merchant with elevated risk or an active incident.
4. Review the incident details and the observed fraud-rate deviation.
5. Open the investigation panel and read the evidence-grounded explanation.
6. Check verification output to see whether the claims are supported by actual evidence.
7. Apply a bounded response action and inspect the audit record.
8. Review the evaluation summary and the held-out methodology description.

## Suggested talking points

- The project is built around explainability and operational honesty.
- The system does not pretend to be a live payment processor.
- The core fraud signal is rooted in deterministic detection and evidence.
- The local ML signal is secondary and transparent.
- Human review is part of the workflow and the audit trail remains visible.

## Demo environment assumptions

- synthetic dataset only
- local SQLite persistence
- no production payment rail access
- no live external inference endpoint required
- Razorpay configuration remains demo/test mode unless explicitly added

## Success criteria

A strong demo outcome is one where the reviewer can clearly see:

- fraud risk is being detected
- evidence is being used to explain the alert
- the system is bounded and auditable
- the final decision remains with the analyst
- the product is honest about scope and limitations
