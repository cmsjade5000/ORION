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
- `scripts/sessions_hygiene.sh` (called by maintenance script in preview mode)
- `scripts/session_maintenance.py` (thresholded apply path for explicit cleanup)

Check-only (safe):
- `scripts/gateway_maintenance_apply.sh`

Apply changes (requires explicit opt-in):
- `AUTO_OK=1 scripts/gateway_maintenance_apply.sh --fix --repair --update --sessions --commit --push --restart`

## Release-Aware Post-Upgrade Checks

When OpenClaw is upgraded on the AEGIS host, do these extra checks before
calling the pass complete:

- Review heartbeat/default-delivery behavior on the upgraded AEGIS host and
  verify that no new direct-delivery default conflicts with the single-bot
  policy.
- Run `openclaw secrets audit` on the AEGIS host and confirm there are no
  unintended secret-materialization regressions.
- Run `openclaw sessions cleanup --dry-run` on the AEGIS host to verify the
  newer cleanup path is healthy before using any enforced cleanup.
- Run `openclaw gateway call status --json` in addition to `openclaw health`
  when validating an upgraded host. In `2026.3.12+`, pairing and operator-scope
  regressions can show up there before they are obvious elsewhere.
- Verify the built-in health endpoints directly:
  - `curl -fsS http://127.0.0.1:18889/readyz`
  - `curl -fsS http://127.0.0.1:18889/healthz`
- Re-run `openclaw security audit --deep` and verify loopback-only findings are
  still the only expected warnings.

Reference:
- `docs/AEGIS_OPENCLAW_RELEASE_NOTES_2026_1_30_to_2026_3_13.md`

## Session Hygiene (2026.3.7+)

OpenClaw 2026.3.7 adds first-class session cleanup commands. This repo now
includes a safe wrapper:

- `scripts/sessions_hygiene.sh`

Read-only preview:

```bash
scripts/sessions_hygiene.sh --agent main --fix-missing
```

Apply session cleanup:

```bash
AUTO_OK=1 scripts/sessions_hygiene.sh --agent main --fix-missing --doctor --apply
```

Deliberate thresholded maintenance path:

```bash
AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root /Users/corystoner/src/ORION --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json
```

What this does:
- runs `openclaw sessions cleanup ... --dry-run` first
- optionally applies `--enforce` cleanup
- optionally runs `openclaw doctor --non-interactive` when `--doctor` is set
- writes `tasks/NOTES/session-maintenance.md` so cleanup remains auditable

Hard rule: do not enable unattended `AUTO_OK` automation until Telegram inbound is verified and you are comfortable with drift.
