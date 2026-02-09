# Incidents (Append-Only)

This file is the git-tracked audit log for:
- operational incidents (gateway restarts, “ORION unreachable”, security alerts), and
- emergency events that bypass normal delegation (example: ATLAS unavailable bypass).

Rules:
- Append-only (do not rewrite history).
- Keep entries short and factual (no secrets, no full tool logs, no stack traces).
- Link follow-up work to Task Packets in `tasks/QUEUE.md` and/or `tasks/INBOX/*.md`.
- Prefer using `scripts/incident_append.sh` to reduce formatting drift.

## Incidents

Use this exact format:

```text
INCIDENT v1
Id: INC-<YYYYMMDD>-<hhmm>-<short> | INC-AEGIS-<YYYYMMDDThhmmssZ>
Opened: <ISO8601 timestamp>
Opened By: ORION | AEGIS
Severity: P0 | P1 | P2
Trigger: <STRING>  (examples: ORION_GATEWAY_RESTART, ORION_UNREACHABLE, AEGIS_SECURITY_ALERT, ATLAS_UNAVAILABLE)
Summary: <one sentence>
Evidence:
- <short facts only>
Actions:
- <what was done, if anything>
Follow-up Owner: ORION | ATLAS | Cory
Follow-up Tasks:
- <task packet link or short description>
Closed: <ISO8601 timestamp or "open">
```
