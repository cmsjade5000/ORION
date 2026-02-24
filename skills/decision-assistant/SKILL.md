---
name: decision-assistant
description: ORION decision memo workflow for personal and professional choices with mandatory intake, mode selection, uncertainty handling, and LEDGER delegation for finance/high-stakes cases.
metadata:
  invocation: user
---

# Decision Assistant (ORION)

Use this skill when the user asks for help deciding between options and wants a clear recommendation.

This skill defines ORION's decision workflow and memo format. It does not replace `decision-kernel`; use `decision-kernel` when weighted scoring/sensitivity analysis is needed.

## Trigger Phrases

Activate when requests include phrases like:
- "help me decide"
- "should I"
- "which option"
- "what should I do"
- "is it worth it"
- "should I buy"
- "make a decision"
- "decision memo"

## Mandatory Intake (Ask 2-4 Questions)

Before recommending, ORION must ask intake questions unless the answer is already present in the user message.

Ask at least 2, and up to 4:
1. What is the objective and decision deadline?
2. What options are you currently considering?
3. What constraints matter most (budget, time, energy, commitments)?
4. What downside is unacceptable if this goes wrong?

If critical info is missing after one follow-up, proceed with explicit assumptions.

## Delegation Rule (Finance/High-Stakes)

If the decision includes money, buying, debt, investment, compensation, legal exposure, or other material downside, ORION must delegate to LEDGER with a `TASK_PACKET v1` after intake.

Minimum delegation packet template:

```text
TASK_PACKET v1
Owner: LEDGER
Requester: ORION
Objective: Evaluate options for this decision and return a recommendation with tradeoffs.
Success Criteria:
- Compare options against explicit criteria.
- Quantify impact where possible.
- Return recommendation, risks, and next action.
Constraints:
- Use only provided inputs and clearly labeled assumptions.
- No irreversible actions.
Inputs:
- User objective, options, constraints, and risk tolerance.
- Any relevant numbers, dates, or commitments.
Risks:
- Missing or uncertain inputs may change ranking.
Stop Gates:
- Any destructive or irreversible action.
Output Format:
- Decision memo with objective, options, criteria, recommendation, risks, next action.
```

## Mode Selection

Use one of two modes:

- Fast mode:
  - For low-stakes or reversible choices.
  - Keep criteria compact (3-4 criteria).
  - Return short memo and one next action.

- Deep mode:
  - For high-stakes, expensive, or hard-to-reverse choices.
  - Use `decision-kernel` structure: criteria weights (sum 100), option scoring, and sensitivity check.
  - Include contingencies and explicit decision boundary.

## Output Format (Always Use)

Return a memo with these sections in order:

1. Objective
2. Options
3. Criteria
4. Recommendation
5. Risks
6. Next Action

Keep language concrete and decision-focused.

## Uncertainty Handling (Explicit)

Always include uncertainty explicitly:
- Assumptions: what was assumed due to missing data.
- Confidence: low/medium/high in the recommendation.
- What changes the decision: top 1-3 facts that could flip the recommendation.

If uncertainty is high, give a provisional recommendation and a reversible next action to reduce uncertainty first.
