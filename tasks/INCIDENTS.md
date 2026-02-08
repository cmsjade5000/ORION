# Incidents (Append-Only)

This file is the audit log for emergency events that bypass normal delegation.

Rules:
- Append-only (do not rewrite history).
- Keep entries short and factual.
- Link to follow-up Task Packets in `tasks/QUEUE.md` or `tasks/INBOX/ATLAS.md`.

## Incidents

Use this exact format:

```text
INCIDENT v1
Id: INC-<YYYYMMDD>-<hhmm>-<short>
Opened: <ISO8601 timestamp>
Opened By: ORION
Severity: P0 | P1
Trigger: ATLAS_UNAVAILABLE
Summary: <one sentence>
Evidence:
- <attempt 1 outcome>
- <attempt 2 outcome>
Bypass Actions:
- <what ORION did directly (NODE/PULSE/STRATUS)>
Stop Gates Hit:
- <any approvals requested, or "none">
Follow-up Owner: ATLAS
Follow-up Tasks:
- <task packet link or short description>
Closed: <ISO8601 timestamp or "open">
```

