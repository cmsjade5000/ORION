# ORION Inbox

## Packets

TASK_PACKET v1
Owner: ORION
Requester: ORION
Notify: telegram
Idempotency Key: recovery:stale:ik-65ed39ff98adf9c3
Packet ID: ik-40d4a02532be92db
Parent Packet ID: ik-65ed39ff98adf9c3
Root Packet ID: ik-65ed39ff98adf9c3
Workflow ID: ik-65ed39ff98adf9c3
Objective: Recover stale delegated workflow for [ATLAS] Translate inbound ops request into a safe execution plan with explicit stop gates.
Success Criteria:
- Determine why the delegated workflow stalled.
- Either resume the workflow or leave a terminal recovery result with a concrete blocker.
Constraints:
- Prefer reversible recovery steps first.
- Preserve packet and ticket history.
Inputs:
- Source packet: tasks/INBOX/ATLAS.md:50
- Current age: 24.0h stale
Risks:
- Duplicate recovery work if this packet is appended more than once.
Stop Gates:
- Any destructive or irreversible change without fresh evidence.
Output Format:
- Short checklist with resume path or blocker.
Recovery Source: tasks/INBOX/ATLAS.md:50

TASK_PACKET v1
Owner: ORION
Requester: ORION
Notify: telegram
Idempotency Key: recovery:stale:ik-f2a9338a659085ae
Packet ID: ik-37f3da1abd36f2d9
Parent Packet ID: ik-f2a9338a659085ae
Root Packet ID: ik-f2a9338a659085ae
Workflow ID: ik-f2a9338a659085ae
Objective: Recover stale delegated workflow for [ATLAS] Translate inbound ops request into a safe execution plan with explicit stop gates.
Success Criteria:
- Determine why the delegated workflow stalled.
- Either resume the workflow or leave a terminal recovery result with a concrete blocker.
Constraints:
- Prefer reversible recovery steps first.
- Preserve packet and ticket history.
Inputs:
- Source packet: tasks/INBOX/ATLAS.md:149
- Current age: 24.0h stale
Risks:
- Duplicate recovery work if this packet is appended more than once.
Stop Gates:
- Any destructive or irreversible change without fresh evidence.
Output Format:
- Short checklist with resume path or blocker.
Recovery Source: tasks/INBOX/ATLAS.md:149
