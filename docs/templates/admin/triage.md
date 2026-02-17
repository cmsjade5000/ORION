# Triage Queue (<YYYY-MM-DD>)

Owner: <name/team>
Input sources: <support/sales/on-call/roadmap>
SLA for triage: <e.g., 2 business days>

## Intake Checklist

- [ ] Clear problem statement and affected users
- [ ] Repro steps / logs / screenshots (if bug)
- [ ] Business impact defined (revenue, churn, compliance, ops load)
- [ ] Acceptance criteria (what "done" means)
- [ ] Dependencies or blockers identified

## Priority Framework

Choose one:

- RICE: Reach x Impact x Confidence / Effort
- WSJF: (Business Value + Time Criticality + Risk Reduction) / Job Size

Example scales:

- Impact: 1=minor, 3=degrades core flow, 5=blocks critical flow
- Confidence: 0.5=low, 0.8=medium, 1.0=high
- Effort: 1=hours, 3=1-3 days, 5=1-2 weeks, 8=multi-week

## Triage Table

| ID | Task | Type | Impact (1-5) | Reach | Confidence | Effort | Score | Priority | Owner | Due | Depends on | Notes |
|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|
| T-001 | <summary> | Bug/Feature/Ops | <n> | <n> | <n> | <n> | <calc> | P0/P1/P2/P3 | <name> | <date> | <id> | <link> |

## Definitions

- P0: production down, security incident, or core flow blocked.
- P1: major degradation or high-value customer impact.
- P2: important but not urgent.
- P3: backlog.

