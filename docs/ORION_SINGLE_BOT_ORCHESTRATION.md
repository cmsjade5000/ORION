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

## Director Model (Preferred)

For operational work, ORION should route through ATLAS:

- ORION → ATLAS (director)
- ATLAS → NODE / PULSE / STRATUS (sub-agents) as needed
- ATLAS → ORION (integrated result)

This keeps ORION focused on user-facing synthesis while ATLAS coordinates internal ops specialists.

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
