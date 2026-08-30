# FraudSpike AI demo

## Demo goal

The demonstration is designed to show a full risk workflow in a local environment:

- detect merchant-level fraud spikes
- surface a risk-scored incident
- investigate the evidence
- verify the supported claims
- apply a bounded response action
- preserve the audit trail

## Demo flow

1. Open the dashboard and confirm the current backend-driven metrics.
2. Select a merchant to inspect the risk profile.
3. Open an active incident.
4. Review the investigation explanation and evidence.
5. Review verification outcomes and supported vs unsupported claims.
6. Apply a bounded response such as verify or resolve.
7. Review the audit trail and evaluation metrics.

## Demo environment

- dataset: synthetic
- environment: demo
- Razorpay: demo/test mode only
- investigation mode: deterministic and evidence-grounded unless an optional external model is configured

## Success criteria

The demo is successful when the product clearly communicates: merchant risk, evidence, verification, bounded response, and auditability without pretending to be a live production system.
