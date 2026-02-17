# Decision Kernel

This document standardizes how LEDGER (and other agents) evaluate tradeoffs.

Goals:
- make assumptions explicit
- separate facts from inferences
- keep outputs auditable and comparable across decisions

## Template

### 1) Objective

- What outcome are we optimizing for?
- Time horizon (days/weeks/months/years)?

### 2) Constraints

- Budget cap (hard/soft)
- Time cap
- Risk tolerance (low/med/high)
- Reversibility requirements (can we undo the decision?)

### 3) Options

List 2-5 concrete options (including “do nothing / wait”).

For each option:
- direct costs
- time/attention costs
- second-order effects (maintenance, switching, lock-in)

### 4) Criteria And Weights

Pick 4-7 criteria and assign weights that sum to 100.

Examples:
- reliability (25)
- time saved per week (25)
- risk of regret (15)
- reversibility (10)
- learning value (10)
- cash impact (15)

### 5) Score Each Option

Score each option 1-5 per criterion (or 1-10 if needed). Provide 1 sentence per score.

### 6) Uncertainty

- Assumptions (bulleted)
- Best/Base/Worst case ranges for the highest-leverage variables
- Sensitivity: which single variable would flip the recommendation?

### 7) Recommendation

- pick a default option
- list 1-2 “if X then choose Y” contingencies
- propose a reversible next step if possible

