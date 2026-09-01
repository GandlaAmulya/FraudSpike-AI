# FraudSpike AI security and safety

## Security posture

FraudSpike AI is built as a local demo and investigation platform, not as a production payment processing system. The project therefore keeps a deliberately narrow security and operational scope.

## Current principles

- keep credentials and secrets out of the frontend and public code
- keep any external payment integration behind the backend boundary
- avoid direct execution of destructive financial actions in the UI
- make all significant workflow actions auditable
- prefer evidence-backed reasoning over opaque automation

## Data handling

The system stores only privacy-safe identifiers and coarse geographic information when needed. It does not collect or persist raw personal data or sensitive account details.

## Demo environment assumptions

- synthetic dataset only
- local persistence only
- no live payment rail access
- no real production credentials assumed
- Razorpay remains demo/test-mode until explicitly configured and validated

## Control boundaries

The platform does not allow unrestricted payment blocking, cancellation, or deletion by default. Review decisions are recorded as analyst actions and remain traceable through the audit system.

## Responsible product framing

This system is built to demonstrate credible fraud-risk operations in a contained environment. It is intentionally honest about its limitations and does not claim live production autonomy.
