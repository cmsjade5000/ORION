# Agent Hierarchy (Local Workspace)

This workspace runs multiple isolated OpenClaw agents on the same Mac mini.

## Roles

- ORION (`agentId: main`): the only user-facing ingress agent.
- ATLAS: operational director and executor.
- NODE / PULSE / STRATUS: internal-only ops sub-agents directed by ATLAS.
- PIXEL / EMBER / LEDGER: internal specialists directly invoked by ORION as needed.

## Chain Of Command

Preferred coordination path:

1. Cory talks to ORION (Slack/Telegram).
2. ORION delegates operational work to ATLAS via a Task Packet.
3. ATLAS delegates sub-tasks to NODE / PULSE / STRATUS via Task Packets.
4. ATLAS returns an integrated result to ORION.
5. ORION communicates externally.

Exceptions:

- ORION may directly invoke NODE / PULSE / STRATUS only for explicit emergency recovery when ATLAS is unavailable.

## Task Packets

- All non-trivial delegation must include a Task Packet (`docs/TASK_PACKET.md`).
- Sub-agent Task Packets must set `Requester: ATLAS`.

## Rationale

- Keeps ORION focused on user-facing synthesis and policy enforcement.
- Gives ATLAS a stable operational surface to manage infra/workflow specialists.
- Reduces duplicated work and conflicting actions from parallel specialist turns.

