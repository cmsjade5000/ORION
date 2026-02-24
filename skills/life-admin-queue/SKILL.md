---
name: life-admin-queue
description: Maintain a rolling life-admin backlog and weekly execution queue for bills, renewals, subscriptions, appointments, and paperwork.
metadata:
  invocation: user
---

# Life Admin Queue

Use this skill to keep personal operations work in a stable queue with clear priorities and safe execution.

## Trigger Phrases

Use when the user asks to:
- "organize my life admin"
- "build my bills and renewals queue"
- "what should I handle today for paperwork"
- "plan this week for subscriptions and appointments"
- "triage my admin backlog"
- "what is urgent this week"

## Admin Item Input Schema

Each item should be captured as one record:

```yaml
id: "LA-YYYYMMDD-01"
title: "Renew car registration"
owner: "Cory"
category: "bill|renewal|subscription|appointment|paperwork|other"
due_date: "2026-03-15"
hard_deadline: true
estimated_effort_minutes: 30
cost_usd: 120
risk_level: "low|medium|high|critical"
status: "backlog|ready|blocked|scheduled|done|canceled"
blocker: ""
next_action: "Pay online at state portal"
notes_ref: "optional pointer only; no secrets"
last_updated: "2026-02-22"
```

Required fields:
- `title`, `owner`, `due_date`, `estimated_effort_minutes`, `cost_usd`, `risk_level`, `status`

## Prioritization Rubric

Score each item daily with:
- `urgency` (1-5)
- `impact` (1-5)
- `effort` (1-5)

Definitions:
- `urgency`
  - 5: overdue or due in 0-2 days
  - 4: due in 3-5 days
  - 3: due in 6-10 days
  - 2: due in 11-21 days
  - 1: due in 22+ days
- `impact`
  - 5: major legal/financial/service risk if missed
  - 4: meaningful penalty or high stress if missed
  - 3: moderate cost or disruption
  - 2: low consequence
  - 1: minimal consequence
- `effort`
  - 5: 121+ minutes
  - 4: 61-120 minutes
  - 3: 31-60 minutes
  - 2: 11-30 minutes
  - 1: 0-10 minutes

Priority formula:
- `priority_score = (urgency * impact) - effort`
- Tie-breakers: earlier `due_date`, then higher `risk_level`, then lower `estimated_effort_minutes`.

## Daily Workflow

1. Capture new items and normalize schema.
2. Re-score all non-done items using the rubric.
3. Build `today_list` with capacity limits:
   - Include all overdue items first.
   - Add highest `priority_score` items until 60-120 minutes of total effort.
   - Include at least one quick win (`effort` 1-2) when possible.
4. Mark blocked items and define one unblock action per blocker.
5. End-of-day update: set new statuses and roll unfinished work forward.

## Weekly Workflow

1. Run a backlog review for all non-done items.
2. Recalculate scores and sort by `priority_score`.
3. Build a `this_week_queue` with realistic capacity (5-8 total items).
4. Reserve specific days for hard deadlines and appointments.
5. Publish blockers list with owner and next action.
6. Archive completed items and carry forward remaining ready items.

## Output Templates

### Today List

```md
# Life Admin - Today
Date: YYYY-MM-DD
Capacity: NN minutes

## Must Do
- [ ] ITEM_ID | Title | Due YYYY-MM-DD | Score N | Effort NNm | Next: action

## Should Do
- [ ] ITEM_ID | Title | Due YYYY-MM-DD | Score N | Effort NNm | Next: action

## Quick Wins
- [ ] ITEM_ID | Title | Effort NNm
```

### This-Week Queue

```md
# Life Admin - This Week
Week of: YYYY-MM-DD

## Queue (Ordered)
1. ITEM_ID | Title | Due YYYY-MM-DD | Score N | Owner X
2. ITEM_ID | Title | Due YYYY-MM-DD | Score N | Owner X

## Scheduled Anchors
- Mon: ITEM_ID, ITEM_ID
- Tue: ITEM_ID
- Wed: ITEM_ID
- Thu: ITEM_ID
- Fri: ITEM_ID
```

### Blockers Report

```md
# Life Admin - Blockers
Date: YYYY-MM-DD

- ITEM_ID | Title
  Blocker: short description
  Owner: name
  Next unblock action: concrete step
  Target unblock date: YYYY-MM-DD
```

## Safety Gates

Before irreversible actions (cancel account, submit legal paperwork, non-reversible payment, contract change):
- Require explicit confirmation in-session: `CONFIRM IRREVERSIBLE: <item_id>`.
- Re-state consequence, amount, and deadline before execution.
- If amount is high (default threshold: USD 200+), require a second explicit confirmation.

Sensitive data handling:
- Never store or echo full card numbers, bank account numbers, SSN, passport number, or full login credentials.
- Use redaction format (example: `****1234`) and reference-only notes.
- Do not place secrets in queue items; store only pointers to secure systems.
- If user asks to transmit sensitive data through insecure channels, refuse and request a safer path.

## Definition Of Done

An item is `done` only when:
- The external action completed (paid/submitted/booked/canceled), and
- Evidence is recorded in `notes_ref` (receipt ID, confirmation code, or source pointer), and
- Follow-up date is set if recurring.
