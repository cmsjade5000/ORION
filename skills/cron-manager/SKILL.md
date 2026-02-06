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
  --message "Run heartbeat using repo HEARTBEAT.md; if idle, return HEARTBEAT_OK."
```

```bash
openclaw cron add \
  --name "ORION daily review (21:00)" \
  --cron "0 21 * * *" \
  --tz "America/New_York" \
  --session isolated \
  --wake "next-heartbeat" \
  --deliver false \
  --message "Review tasks/QUEUE.md; summarize progress and propose next steps."
```

## Guardrails

- Default `deliver=false` unless Cory explicitly wants a notification.
- Avoid high-frequency schedules until the system is stable.
- Keep cron payloads bounded; do not browse endlessly.
