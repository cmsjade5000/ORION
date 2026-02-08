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

## ATLAS Unavailable Threshold

ORION treats ATLAS as unavailable when:

1. ORION attempts an "ATLAS ping" twice, and
2. both attempts fail to receive `ATLAS_OK` within 90 seconds, and
3. the two attempts occur within a 5-minute window.

ATLAS ping is a minimal Task Packet to ATLAS that requires one-line output:

```text
TASK_PACKET v1
Owner: ATLAS
Requester: ORION
Severity: P1
Objective: Return ATLAS_OK if you are available.
Success Criteria:
- Output exactly: ATLAS_OK
Constraints:
- No external messaging.
Inputs:
- none
Risks:
- low
Stop Gates:
- none
Output Format:
- One line only.
```

## Emergency Bypass (Auditable)

When ATLAS is unavailable:

1. ORION opens an incident by appending an entry to `tasks/INCIDENTS.md`.
2. ORION may directly invoke `NODE`, `PULSE`, and/or `STRATUS` only for reversible, diagnostic, or recovery tasks.
3. ORION includes `Emergency: ATLAS_UNAVAILABLE` and `Incident: <id>` in the Task Packet.
4. ORION assigns a post-incident review to ATLAS (once ATLAS is back) with follow-up fixes and prevention steps.

## Rationale

- Keeps ORION focused on user-facing synthesis and policy enforcement.
- Gives ATLAS a stable operational surface to manage infra/workflow specialists.
- Reduces duplicated work and conflicting actions from parallel specialist turns.
