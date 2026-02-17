---
name: discovery-scorecard
description: PIXEL signal-vs-hype and relevance scoring template (with evidence/freshness hooks) for turning ideas into actionable briefs.
metadata:
  invocation: user
---

# Discovery Scorecard (PIXEL)

Use this skill to rank “interesting” discoveries by Cory-fit and durability, and to convert them into an ORION-usable handoff.

## Labels

- `validated`: strong evidence and adoption; low hype risk
- `emerging`: plausible, early signal; moderate uncertainty
- `speculative`: weak evidence or high churn; treat as an experiment only

## 5-Factor Score (1-5 each)

1. Cory-fit (workflow/context match)
2. Practical value (expected benefit)
3. Time-to-try (can we test in 30 minutes?)
4. Ecosystem momentum (maintainers/users, not just chatter)
5. Durability (risk of being a short-lived trend)

Total: 5 to 25.

## Evidence Hook (Recommended)

For anything phrased as “latest/updated/new”, require:
- at least one link per concrete claim
- a `published_at` timestamp with timezone

If you have multiple items, validate with:

```bash
python3 scripts/evidence_check.py --input evidence.json
```

## Discovery-to-Action Handoff Template

Idea:
Why now:
Who it’s for:
First 30-minute test:
Success signal:
Risks / stop conditions:
Owner handoff:

