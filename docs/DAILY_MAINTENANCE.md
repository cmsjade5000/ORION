# Daily Maintenance (AEGIS Monitors, ORION Executes)

Goal: AEGIS monitors OpenClaw update/security posture and raises a HITL plan; ORION/ATLAS decides whether to apply fixes/updates, commit/push, and restart the gateway.

## Why This Shape

- **Single-bot Telegram policy:** only ORION posts to Telegram.
- **AEGIS policy:** alert-only for changes; it may create a plan artifact, but should not auto-fix or auto-update.

## AEGIS (Hetzner) Daily Monitor

Script:
- `scripts/aegis_remote/aegis-maintenance-orion`

Behavior:
- Runs **read-only** over restricted SSH to the Mac mini:
  - `openclaw security audit --deep --json`
  - `openclaw update status`
- If there are actionable findings, writes a plan on the AEGIS host:
  - `/var/lib/aegis-sentinel/defense_plans/INC-AEGIS-MAINT-*.md`

Deploy:
- `scripts/deploy_aegis_remote.sh`

Systemd (Hetzner) suggested units:
- `aegis-maintenance-orion.timer` (daily)
- `aegis-maintenance-orion.service`

## ORION Follow-Up Message (Telegram Group Chat)

Use ORION to watch for new plans and post a follow-up message.

Recommended OpenClaw cron job (every 30 minutes):

```bash
openclaw cron add \
  --name "aegis-defense-watch" \
  --description "Watch AEGIS plans and notify via ORION Telegram bot" \
  --every "30m" \
  --agent main \
  --session isolated \
  --no-deliver \
  --wake "next-heartbeat" \
  --message "Run ORION_TELEGRAM_CHAT_ID=<GROUP_CHAT_ID> scripts/aegis_defense_watch.sh. Respond NO_REPLY."
```

Notes:
- Set `ORION_TELEGRAM_CHAT_ID` to your **Telegram group** chat id.
- If you omit it, the watch script falls back to `AEGIS_TELEGRAM_CHAT_ID` from the Hetzner env (often a DM chat id).

## Applying Fixes/Updates (Manual, Gated)

Script (runs on the Mac mini):
- `scripts/gateway_maintenance_apply.sh`

Check-only (safe):
- `scripts/gateway_maintenance_apply.sh`

Apply changes (requires explicit opt-in):
- `AUTO_OK=1 scripts/gateway_maintenance_apply.sh --fix --repair --update --commit --push --restart`

Hard rule: do not enable unattended `AUTO_OK` automation until Telegram inbound is verified and you are comfortable with drift.
