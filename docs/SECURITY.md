# FraudSpike AI security and safety

## Safety principles

- Do not expose credentials in the frontend.
- Keep all external payment integrations behind the backend.
- Maintain a bounded response policy.
- Default to evidence-grounded investigation.
- Label synthetic/demo data clearly.

## Current environment

The product is running in a local demo mode. No live payment rail or production Razorpay credentials are assumed.

## Operational guardrails

The system does not allow unrestricted financial auto-actions. Analysis is evidence-based and response actions remain deterministic and bounded.
