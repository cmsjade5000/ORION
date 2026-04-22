# Native Subagent Control Plane

Purpose: define the default ORION-core control flow for active delegated sessions without replacing Task Packets as the durable async record.

## Default stance

- ORION is the top-level router and user-facing ingress.
- ATLAS is the only recursive orchestrator in ORION core.
- Native subagent control is the default for active sessions:
  - `sessions_spawn`
  - `sessions_yield`
  - optional `subagents list`
  - optional `subagents steer`
  - optional `subagents kill`
- Task Packets remain the durable record for intent, constraints, evidence, and recovery.
- ACPX stays a bounded ATLAS-owned pilot for coding/review isolation and is not the default specialist delegation path.

## Control flow

1. ORION writes or references a Task Packet.
2. ORION spawns the specialist with `sessions_spawn`.
3. If the work is still active after correct scoping, ORION yields the current turn with `sessions_yield`.
4. ORION or ATLAS uses `subagents list` only when bounded inspection is needed.
5. ATLAS may use `subagents steer` only for narrow corrective input.
6. ORION or ATLAS may use `subagents kill` only for explicit cancellation, recovery, or clear runaway work.
7. The specialist returns one integrated result to ORION.

## Ownership rules

- ORION may spawn specialists, but does not recursively orchestrate internal workers.
- ATLAS may recursively orchestrate `node`, `pulse`, and `stratus`.
- Non-ATLAS specialists should not recursively orchestrate child subagents in ORION core.
- Specialists never message Cory directly.

## Failure and recovery

- If a child session stalls, inspect first with `subagents list`.
- If the child is salvageable, use one bounded `subagents steer` correction rather than re-spawning immediately.
- If the child is no longer safe or useful, use `subagents kill`, record the cancellation in status notes or job tracking, and decide whether to re-spawn from the same Task Packet.
- If work must survive beyond the current session, rely on the Task Packet and repo-backed reconcile loop rather than assuming session-native state is durable enough on its own.

## Validation posture

- Prefer local/read-only validation for control-plane changes.
- Do not add automatic OpenAI or Codex smoke turns for this workflow.
- Keep ACPX validation bounded to its existing local/runtime checks.
