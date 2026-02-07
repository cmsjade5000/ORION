# Working Memory

## Current Goal

Go live locally on the Mac mini:

- ORION is the only Telegram-facing bot.
- Specialists run as isolated OpenClaw agents (`atlas`, `node`, `pulse`, etc.) with ORION delegating via Task Packets.

## Current Status

- OpenClaw workspace points at this repo.
- Isolated specialist agents are configured locally.

## Known Blockers / Risks

- Gateway service is not installed/running persistently yet (cron + agentToAgent reliability depends on this).
- Ensure no secrets ever land in Git (run `skills/secrets-scan` before pushes).

## Next Steps (Go-Live Checklist)

1. Install + start the gateway service:
   - `openclaw gateway install`
   - `openclaw gateway start`
2. Run hardening checks:
   - `openclaw doctor --repair`
   - `openclaw security audit --deep`
3. Verify Telegram channel health:
   - `openclaw channels status --probe`
4. Verify delegation:
   - ORION sends one Task Packet to `atlas` and receives a result.
5. Add minimal cron jobs (deliver=false by default):
   - heartbeat (15m)
   - daily review (21:00 America/New_York)
