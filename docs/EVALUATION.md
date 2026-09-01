# FraudSpike AI evaluation approach

## Objective

The evaluation flow is designed to measure whether the merchant-level fraud spike detector performs well on a truly held-out set while keeping the result understandable and trustworthy.

## Methodology

The project uses a train/validation/test split and evaluates the merchant-window detector only on the held-out test set. The logic is aligned with a standard defensive evaluation workflow:

- train on a historical period
- select policy using validation data
- evaluate on a final held-out period
- report confusion-matrix-based metrics only when those values are calculated
- keep false-positive cost visible instead of hiding it

## What is intentionally not claimed

This project does not claim production-ready loss metrics or a live fraud model accuracy. The evaluation is designed to be honest and local.

The metrics remain nullable until an evaluation actually runs. This keeps the model and domain contracts accurate and avoids fake placeholder values.

## Product meaning

The evaluation layer exists to support credible reporting, not to create a false sense of certainty. It shows that the project can describe its performance honestly and make operational trade-offs visible.

## How the UI and API present it

The backend and frontend both surface the evaluation summary in a structured way, including:

- confusion matrix values
- precision
- recall
- F1
- false-positive cost estimate
- held-out test-set metadata

The result is an operationally honest view of model performance rather than a polished but misleading metric sheet.
