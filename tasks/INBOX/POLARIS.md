# POLARIS Inbox

POLARIS is internal-only. ORION assigns admin co-pilot workflows here.

Scope examples:
- reminders/calendar workflow orchestration
- contact organization and follow-through tracking
- email-prep packet coordination

Append new Task Packets below. Spec: `docs/TASK_PACKET.md`.

Queue policy (enforced):
- Max active packets in this inbox: 8.
- Age bands: `0-24h` normal, `>24h` amber, `>48h` red, `>72h` gatekeeper escalation, `>120h` incident required.
- Backup takeover and gatekeeper authority follow `docs/AGENT_OWNERSHIP_MATRIX.md`.

Milestone update protocol:
- For rollout/admin packets that should notify Cory, include `Notify: telegram`.
- Keep milestone labels bounded:
  - `Scaffold complete`
  - `Routing + gates complete`
  - `Tests green + config active`

## Weekly Routing Audit Runbook

Run location:
- ORION main workspace session at `/Users/corystoner/Desktop/ORION`.

Cadence:
- Weekly (Friday ET recommended).

ORION report format (concise):
- `Queue: <active>/<max> (max=8), oldest=<age>`
- `Aging bands: >24h=<n>, >48h=<n>, >72h=<n>, >120h=<n>`
- `Escalations: <none|list>`
- `Routing fixes: <none|list>`
- `Next actions: <1-3 bullets>`

## Packets
