# FraudSpike AI evaluation

## Objective

The evaluation flow measures whether the merchant-level fraud-spike detector identifies risky merchants while preserving operational defensibility and honest cost reporting.

## Held-out evaluation

Current evaluation values reported by the backend pipeline:

- TP: 452
- FP: 820
- TN: 1092
- FN: 8
- Precision: 35.53%
- Recall: 98.26%
- F1: 52.19%
- False-positive cost: ₹102,500
- Test set size: 2,372

## Confusion matrix

                 PREDICTED
               SAFE   FRAUD
ACTUAL SAFE    TN=1092  FP=820
ACTUAL FRAUD   FN=8    TP=452

## Interpretation

High recall is desirable for a fraud defense product because missed fraudulent spikes can be costly. At the same time, the false-positive burden remains meaningful, which is why the project keeps the cost estimate visible and does not hide the operational trade-off.

## Product meaning

This is a useful product story for a fraud-risk system because it demonstrates a measured trade-off rather than a misleadingly perfect detector. The product is telling the truth about performance and operational cost.
