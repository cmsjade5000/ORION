# ORION Single-Bot Orchestration

## Purpose

Define how ORION operates when it is the only Telegram-enabled bot.

## Runtime Model

- User-facing channel access: ORION only
- Specialist reasoning: isolated OpenClaw agents (internal-only)
- AEGIS: remote sentinel only (monitor/revive), not a user-facing chat bot

## Orchestration Flow

1. ORION receives user request.
2. ORION decides direct answer vs specialist delegation.
3. If delegation is needed:
   - Preferred: delegate via `sessions_spawn` using a Task Packet.
   - Optional: swarm planning (`swarm-planner`) and parallel execution (`parallel-task`) when you explicitly want it.
   - Fallback: append a Task Packet to `tasks/INBOX/<AGENT>.md` and run the specialist turn manually with `openclaw agent --agent <id> ...` (do not deliver to Telegram).
4. ORION sends a Task Packet (per `docs/TASK_PACKET.md`) and links any task-specific files.
5. ORION collects outputs, resolves conflicts, and returns one response to the user.

## Mandatory News Pipeline (Sourced)

To prevent plausible-but-wrong headlines:

1. Retrieval first (preferred: deterministic RSS scripts; otherwise WIRE with links).
2. Draft second (SCRIBE).
3. Send last (ORION).

## Director Model (Preferred)

For operational work, ORION should route through ATLAS:

- ORION → ATLAS (director)
- ATLAS → NODE / PULSE / STRATUS (sub-agents) as needed
- ATLAS → ORION (integrated result)

This keeps ORION focused on user-facing synthesis while ATLAS coordinates internal ops specialists.

Administrative load routing:
- Recurring triage (cron/heartbeat/queue scanning): ATLAS → PULSE.
- Task/incident organization (“paperwork”): ATLAS → NODE.

## POLARIS Admin Co-Pilot Model

For day-to-day admin workflows, ORION can route through POLARIS:

- ORION -> POLARIS (admin workflow orchestrator)
- POLARIS -> ATLAS (execution path for workflow automation/cron/ops tasks) as needed
- POLARIS -> SCRIBE (send-ready drafts) as needed
- POLARIS -> ORION (integrated status + next steps)

Boundary rules:
- POLARIS is internal-only and never messages Cory directly.
- ORION remains the only external messenger.
- Side effects stay confirmation-gated by default.

Kalshi boundary:
- Routine operations/diagnostics: ORION -> ATLAS -> STRATUS/PULSE.
- Policy/risk/parameter changes: LEDGER gate first, then ATLAS execution.

## Ownership And Queue Controls

- Ownership matrix: `docs/AGENT_OWNERSHIP_MATRIX.md`
- POLARIS queue thresholds: `src/agents/POLARIS.md`
- POLARIS queue runbook and audit format: `tasks/INBOX/POLARIS.md`

## Weekly Routing Audit Runbook

Run location:
- ORION main workspace session in `/Users/corystoner/Desktop/ORION`.
- Audit target: `tasks/INBOX/POLARIS.md` against ownership rules in `docs/AGENT_OWNERSHIP_MATRIX.md`.

Cadence:
- Weekly (Friday ET recommended).

Required concise ORION report:
- `Queue: <active>/<max> and oldest age`
- `Aging: >24h=<n>, >48h=<n>, >72h=<n>, >120h=<n>`
- `Escalations: <none|list>`
- `Misroutes and fixes: <none|list>`
- `Next actions: <1-3 bullets>`

## Milestone Telegram Update Protocol

When rollout/admin packets include `Notify: telegram`, ORION should send milestone updates at bounded checkpoints:
- `Scaffold complete`
- `Routing + gates complete`
- `Tests green + config active`

Avoid high-frequency chatter; use milestone checkpoints only.

## ATLAS Unavailable + Emergency Bypass (Auditable)

Normal rule: ORION routes ops/infra/workflow work through ATLAS.

Emergency bypass rule: ORION may directly invoke `NODE`/`PULSE`/`STRATUS` only when ATLAS is unavailable per `docs/AGENT_HIERARCHY.md`, and only for reversible diagnostic or recovery actions.

Requirements:
- Open an incident log entry in `tasks/INCIDENTS.md`.
- Include `Emergency: ATLAS_UNAVAILABLE` and `Incident: <id>` in the Task Packet.
- After recovery, assign a post-incident review to ATLAS with prevention actions.

## Non-Negotiables

- Specialists never message Telegram directly in current mode.
- ORION keeps final authority with Cory and applies confirmation gates for risky actions.
- All specialist outputs are treated as inputs to ORION synthesis, not direct user responses.
