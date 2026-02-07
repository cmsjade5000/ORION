---
name: cron-manager
description: Create/audit/disable OpenClaw cron jobs safely with guardrails. Use for heartbeat-driven automation.
metadata:
  invocation: user
---

# Cron Manager

This repo uses OpenClaw cron jobs to run "agent turns" on a schedule. Cron only fires reliably if the gateway service is installed and running.

## List Jobs

```bash
openclaw cron list
```

If that fails, check gateway service status:

```bash
openclaw gateway status
```

## Disable A Job

Prefer disabling over deleting:

```bash
openclaw cron disable --id <job-id>
```

## Create A Job (Template)

Examples (pick one):

```bash
openclaw cron add \
  --name "ORION heartbeat (15m)" \
  --every "15m" \
  --session isolated \
  --wake "next-heartbeat" \
  --deliver false \
  --message "$(cat <<'MSG'
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Run heartbeat once and update tasks/QUEUE.md if needed.
Success Criteria:
- Returns HEARTBEAT_OK when idle.
- Updates tasks/QUEUE.md only when there is a clear Ready item.
Constraints:
- Do not browse endlessly.
- Do not message Telegram unless explicitly asked in the task.
Inputs:
- HEARTBEAT.md
- tasks/QUEUE.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any credential change.
Output Format:
- Short checklist of what was checked + what changed.
MSG
)"
```

```bash
openclaw cron add \
  --name "ORION daily review (21:00)" \
  --cron "0 21 * * *" \
  --tz "America/New_York" \
  --session isolated \
  --wake "next-heartbeat" \
  --deliver false \
  --message "$(cat <<'MSG'
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Review tasks/QUEUE.md and propose the next 1-3 highest leverage tasks.
Success Criteria:
- Produces a short summary + next steps.
Constraints:
- No browsing unless required.
Inputs:
- tasks/QUEUE.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any credential change.
Output Format:
- Bullet summary + next actions.
MSG
)"
```

## Guardrails

- Default `deliver=false` unless Cory explicitly wants a notification.
- Avoid high-frequency schedules until the system is stable.
- Keep cron payloads bounded; do not browse endlessly.
