# POLARIS Admin Workflows

POLARIS is the default internal route for ORION's admin-copilot work.

## Default Routing

Use POLARIS first for:
- reminders and recurring task prep
- calendar hygiene and daily agenda prep
- Notes capture and follow-up tracking
- email preparation
- "what should I do today?" style requests

Keep side effects confirmation-gated. The default mode is prepare, classify, queue, and draft.

## Canonical Packet Templates

All POLARIS packets should include:
- `Notify: telegram`
- `Opened: YYYY-MM-DD`
- `Due: YYYY-MM-DD`
- `Execution Mode: direct|delegate`
- `Tool Scope: read-only|write`

### Capture

Use when Cory wants to save something quickly for later triage.

```text
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-03-12
Due: 2026-03-14
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- Capture is classified.
- Next safe step is identified.
Constraints:
- Prepare/draft first.
Inputs:
- tasks/INTAKE/...
Risks:
- low
Stop Gates:
- Any external side effect.
Output Format:
- Result block with classification and next step.
```

### Today Agenda

Use when Cory asks what to do today.

```text
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-03-12
Due: 2026-03-12
Execution Mode: direct
Tool Scope: read-only
Objective: Prepare today's agenda from calendars, reminders, delegated work, and open follow-through.
Success Criteria:
- Returns one concise agenda.
- Highlights top next actions and blockers.
Constraints:
- No external writes.
Inputs:
- tasks/NOTES/assistant-agenda.md
- memory/ASSISTANT_PROFILE.md
Risks:
- stale local state
Stop Gates:
- Any side-effectful action.
Output Format:
- Result block with agenda bullets and approval gates if needed.
```

### Follow-Up Chase

Use when an item is waiting on another person or system.

### Weekly Review

Use when Cory wants admin reset, cleanup, and next actions.

### Email Prep

Use when ORION needs a safe, send-ready draft before any outbound send.
