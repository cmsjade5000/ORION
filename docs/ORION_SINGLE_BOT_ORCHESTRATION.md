# ORION Single-Bot Orchestration

## Purpose

Define how ORION operates when it is the only Telegram-enabled bot.

For the first-time onboarding and check path, start at [docs/ORION_START_HERE.md](/Users/corystoner/src/ORION/docs/ORION_START_HERE.md).

## Runtime Model

- User-facing channel access: ORION only
- Core specialist reasoning: isolated OpenClaw agents (internal-only)
- AEGIS: remote sentinel only (monitor/revive), not a user-facing chat bot

Default ORION core routing lanes:
- ATLAS
- POLARIS
- WIRE
- SCRIBE

Optional retained lanes:
- LEDGER
- EMBER

Implementation-detail lanes behind ATLAS:
- NODE
- PULSE
- STRATUS

Non-core extension lanes:
- PIXEL
- QUEST

## Orchestration Flow

1. ORION receives user request.
2. ORION decides direct answer vs specialist delegation.
3. If delegation is needed:
   - Preferred: delegate via `sessions_spawn` using a Task Packet.
   - For active long-running delegated work, suspend the current turn with `sessions_yield` after the child is correctly scoped.
   - Use `subagents list` for bounded state inspection, `subagents steer` for bounded correction, and `subagents kill` for explicit cancel/recovery.
   - Do not treat `sessions_yield` as the durable system of record; use packet-backed reconciliation for work that must survive beyond the current session.
   - Read delegated-work state from `tasks/JOBS/<job>.json`, `tasks/JOBS/wf-*.json`, and `tasks/JOBS/summary.json`; inbox markdown is the input/log surface, not the canonical read-time model.
   - Optional: swarm planning (`swarm-planner`) and parallel execution (`parallel-task`) when you explicitly want it.
   - Fallback: append a Task Packet to `tasks/INBOX/<AGENT>.md` and run the specialist turn manually with `openclaw agent --agent <id> ...` (do not deliver to Telegram).
4. ORION sends a Task Packet (per `docs/TASK_PACKET.md`) and links any task-specific files.
5. ORION collects outputs, resolves conflicts, and returns one response to the user.

## Core Boundary

ORION core is the admin-copilot control plane. Trading, gaming, recommendation, and media mini-flows should not widen the default routing surface or default Telegram command set.

Use `docs/ORION_EXTENSION_SURFACES.md` when a non-core product surface still needs a bounded handoff from core.

### PDF And File Review Path (2026.3.2)

When Cory asks ORION to review a PDF or file-heavy artifact:

1. ORION keeps the user-facing thread.
2. ORION delegates via `sessions_spawn` with a Task Packet.
3. ORION attaches the source file inline to the subagent session when the file is needed for direct inspection.
4. The specialist uses the `pdf` tool (or other file-aware tooling) and returns a concise result to ORION only.
5. ORION sends the integrated summary back to Cory.

See:
- `docs/PDF_REVIEW_WORKFLOW.md`

### Brokered File Transfer Path

When Cory asks ORION to move, fetch, inspect, or stage files across paired nodes:

1. ORION keeps the user-facing thread and decides whether the file-transfer broker is warranted.
2. ORION delegates execution to ATLAS with a Task Packet using `docs/ORION_FILE_TRANSFER_BROKER.md`.
3. ATLAS may route node or gateway details to STRATUS, but ATLAS remains responsible for the result.
4. Read operations use `dir_list`, `file_fetch`, or `dir_fetch`; writes use `file_write` only inside broker inbound staging.
5. Writes require `Approval Gate: CORY_MINIAPP_APPROVED` and proof before ORION reports `verified`.

Freeform node-to-node file movement is not part of ORION core.

## Mandatory News Pipeline (Sourced)

To prevent plausible-but-wrong headlines:

1. Retrieval first (preferred: deterministic RSS scripts; otherwise WIRE with links).
2. Draft second (SCRIBE).
3. Send last (ORION).

## Director Model (Preferred)

For operational work, ORION should route through ATLAS:

- ORION → ATLAS (director)
- ATLAS → NODE (packet and incident hygiene) / PULSE (queueing and retries) / STRATUS (host implementation) as needed
- ATLAS → ORION (integrated result)

This keeps ORION focused on user-facing synthesis while ATLAS coordinates internal ops specialists.
ATLAS is the only recursive orchestrator in ORION core; ORION itself stays non-recursive.

Delegated-job convergence rule:
- notifier and operator-status surfaces should consume the `tasks/JOBS` read model first
- stable queued/result digests and safe result previews belong to job artifacts, not ad hoc inbox rescans

Administrative load routing:
- Recurring triage (cron/heartbeat/queue scanning): ATLAS → PULSE.
- Queue aging and retry staging: ATLAS → PULSE.
- Task packet and incident organization (“paperwork”): ATLAS → NODE.
- Day-to-day assistant work (today agenda, quick capture, follow-through, email prep): ORION -> POLARIS first.
- External fact validation and current release/tool verification: ORION -> WIRE.
- Discovery and gaming requests are off-core extension work; do not route them by default in ORION core.

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
- Long admin work should still preserve durable state via Task Packets or queue artifacts rather than assuming session-native yield is the durable system of record.

Kalshi boundary:
- Routine operations/diagnostics: ORION -> ATLAS -> STRATUS/PULSE.
- Policy/risk/parameter changes: LEDGER gate first, then ATLAS execution.

## Ownership And Queue Controls

- Ownership matrix: `docs/AGENT_OWNERSHIP_MATRIX.md`
- POLARIS queue thresholds: `src/agents/POLARIS.md`
- POLARIS queue runbook and audit format: `tasks/INBOX/POLARIS.md`

## Weekly Routing Audit Runbook

Run location:
- ORION main workspace session in `/Users/corystoner/src/ORION`.
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
