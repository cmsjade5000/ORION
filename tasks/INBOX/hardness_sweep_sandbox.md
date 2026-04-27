# Inbox Sweep Sandbox

## Packets

TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Synthetic lifecycle sweep for inbox queue migration.
Notify: telegram
Success Criteria:
- inbox_cycle processes this packet into tasks/JOBS artifacts.
- Synthetic packet transitions to pending_verification once Result appears.

Result:
- Status: OK
- What changed / what I found:
  - Synthetic lifecycle result appended by sweep script.
