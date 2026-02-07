# ORION Single-Bot Orchestration

## Purpose

Define how ORION operates when it is the only Telegram-enabled bot.

## Runtime Model

- User-facing channel access: ORION only
- Specialist reasoning: internal sessions only
- AEGIS: remote sentinel only (monitor/revive), not a user-facing chat bot

## Orchestration Flow

1. ORION receives user request.
2. ORION decides direct answer vs specialist delegation.
3. If delegation is needed:
   - Preferred: swarm planning (`/swarm-planner` or `/plan` in swarm mode), then `/parallel-task`
   - Fallback: native session tools (`sessions_spawn`, `sessions_send`, `session_status`, `sessions_history`, `sessions_list`)
4. ORION seeds each specialist session with:
   - `agents/<AGENT>/SOUL.md`
   - `SECURITY.md`
   - `TOOLS.md`
   - `USER.md`
   - A Task Packet (per `docs/TASK_PACKET.md`) + any task-specific files
5. ORION collects outputs, resolves conflicts, and returns one response to the user.

## Non-Negotiables

- Specialists never message Telegram directly in current mode.
- ORION keeps final authority with Cory and applies confirmation gates for risky actions.
- All specialist outputs are treated as inputs to ORION synthesis, not direct user responses.
