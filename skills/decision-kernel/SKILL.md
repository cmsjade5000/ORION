---
name: decision-kernel
description: Standard decision framework for LEDGER/ORION/PIXEL: objective, constraints, option scoring, uncertainty, sensitivity, recommendation.
metadata:
  invocation: user
---

# Decision Kernel

Use this skill when decisions, tradeoffs, prioritization, or “should I do/buy X?” questions are central.

## Source Of Truth

- `/Users/corystoner/Desktop/ORION/docs/DECISION_KERNEL.md`

## Output Shape (Recommended)

- Objective
- Constraints
- Options
- Criteria + weights (sum to 100)
- Scoring table (option x criterion)
- Uncertainty (assumptions + best/base/worst)
- Recommendation + contingencies

## Optional Helper

If you have structured numbers, you can use:

```bash
python3 scripts/sensitivity_matrix.py --input decision.json
```

