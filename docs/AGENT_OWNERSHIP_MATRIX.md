# Agent Ownership Matrix

This matrix defines strict ownership for recurring workflows.

Role meanings:
- Primary: default owner that executes and reports status.
- Backup: takes over when aging/escalation thresholds are hit or the primary is unavailable.
- Gatekeeper: approval authority for side effects, policy changes, or risk acceptance.

| Workflow | Primary | Backup | Gatekeeper |
| --- | --- | --- | --- |
| Reminder/cron intake and packet preparation | POLARIS | ATLAS | ORION |
| Reminder/cron execution and verification | ATLAS | PULSE | ORION |
| Calendar hygiene and weekly preparation | POLARIS | ATLAS | ORION |
| Email draft preparation | POLARIS | SCRIBE | ORION |
| External message sending (Telegram/Discord/email) | ORION | none (single-bot constraint) | ORION |
| Task packet and incident record hygiene (repo artifacts) | NODE | ATLAS | ORION |
| Contact registry updates (repo artifacts) | POLARIS | ATLAS | ORION |
| Follow-through notifier policy and queue maintenance | POLARIS | ATLAS | ORION |
| Browser-led direct interaction workflows | ATLAS | POLARIS | ORION |
| Local device-node action execution | ATLAS | STRATUS | ORION |
| Scheduled workflow queueing and retry staging | PULSE | ATLAS | ORION |
| Direct-interaction proof bundle review | ORION | ATLAS | ORION |
| Routing and hierarchy policy edits | ORION | POLARIS | Cory (via ORION) |
| Kalshi routine diagnostics and operations | ATLAS | STRATUS | ORION |
| Kalshi policy/risk/parameter changes | LEDGER | ORION | Cory (via ORION) |

Enforcement rules:
- Every non-trivial Task Packet must map to one row in this matrix.
- Queue aging and escalation uses POLARIS thresholds in `src/agents/POLARIS.md`.
- Backups inherit ownership only after the documented threshold or explicit ORION reassignment.
- Device-control packets should also carry `Device Target`, `Action Class`, and `Action Id` when relevant so the row mapping is reviewable.
