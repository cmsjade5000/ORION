# Assistant Skill Shortlist

These are the default high-signal skills for the admin-copilot posture.

## ORION
- `agentmail`
- `apple-notes`
- `apple-reminders`
- `things-mac`
- `task-packet-guard`
- `daily-briefing`

## POLARIS
- `apple-notes`
- `apple-reminders`
- `things-mac`
- `agentmail`
- `task-packet-guard`
- `session-logs`

## Maintenance

Monthly review:

```bash
./scripts/assistant_skill_refresh.sh
```

Apply only after review:

```bash
./scripts/assistant_skill_refresh.sh --apply
```
