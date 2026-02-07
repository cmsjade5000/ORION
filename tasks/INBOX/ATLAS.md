# ATLAS Inbox

Append new Task Packets below. Spec: `docs/TASK_PACKET.md`.

Example:

```text
TASK_PACKET v1
Owner: ATLAS
Requester: ORION
Objective: Install and start the OpenClaw gateway service on macOS.
Success Criteria:
- `openclaw gateway status` shows running.
Constraints:
- Keep gateway bind loopback.
Inputs:
- docs/WORKFLOW.md
Risks:
- low
Stop Gates:
- Any network exposure change.
Output Format:
- Commands run + resulting status output.
```

## Packets
