# FraudSpike AI limitations and scope

## Current scope

FraudSpike AI is intentionally designed as a local demo platform and not as a production payment processor.

Current boundaries include:

- synthetic data only
- no live payment rail access
- no production payment credentials or live bank integration
- no real-time production monitoring environment
- no live external LLM dependency required for the core investigation flow
- bounded defensive actions only, not autonomous destructive payment controls

## Operational limitations

The system uses structured local data and deterministic detection logic. This is appropriate for a demo and a credible portfolio project, but it does not represent a full-scale fraud operating environment.

## Evidence and model limits

- the local anomaly signal is supplementary and depends on available merchant history
- if there is insufficient evidence, the system remains explicit instead of pretending certainty
- the project avoids claiming calibrated fraud probability or production-grade model accuracy
- evaluation metrics are reported only when the held-out evaluation is genuinely computed

## Why these limits matter

This honesty is part of the product’s value. A strong fraud investigations system should be clear about what is being measured, what is supported by evidence, and what remains a human decision.
