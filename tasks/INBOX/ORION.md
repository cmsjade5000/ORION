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
