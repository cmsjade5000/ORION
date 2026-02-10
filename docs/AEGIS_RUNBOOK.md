# AEGIS Runbook (Remote Sentinel)

This doc describes the current AEGIS deployment and how to operate it **without** hardcoding secrets into the repo.

AEGIS is a remote sentinel hosted on a Hetzner Ubuntu server. It provides:
- Availability: monitor ORION and restart ORION’s OpenClaw gateway if unhealthy.
- Security signals: detect suspicious events and configuration drift (alert-only).

AEGIS is **alert-only** for security findings (no defensive actions), except for:
- Restarting ORION’s OpenClaw gateway (availability).
- Restarting AEGIS’ own OpenClaw gateway if it is down.

## Topology (Current)

As of 2026-02-08:
- AEGIS host: Hetzner Ubuntu 24.04 (systemd)
  - Tailscale: `ubuntu-4gb-hel1-9` (`100.75.104.54`)
- ORION host: Mac mini (launchd)
  - Tailscale: `mac-mini` (`100.112.98.18`)

Notes:
- Prefer Tailscale IPs/hostnames. Public IPs and hostnames may change after rebuilds.

## Policy Notes (Single-Bot Telegram Mode)

This workspace’s default posture is “single-bot Telegram”:
- ORION is the only user-facing Telegram bot.
- Specialists do not DM Cory directly in Telegram.

Implication for AEGIS alerting:
- Prefer Slack alerts from AEGIS (or no outbound alerts).
- If you enable Telegram alerts from the Hetzner host anyway, use them only for critical P0 “ORION unreachable” scenarios, and treat the Telegram token on the Hetzner host as sensitive credential material.

## Services (Hetzner)

These are installed as `systemd` units and are enabled at boot.

OpenClaw Gateway (AEGIS):
- Unit: `openclaw-aegis.service`
- Bind: loopback only
- Port: `18889`
- Auto-restart: `Restart=always` with backoff + `StartLimit*` storm control
- Status:
  - `systemctl status openclaw-aegis.service`
  - `sudo -u aegis -H openclaw gateway probe --port 18889 --bind loopback`

Availability monitor (ORION health + restart):
- Timer: `aegis-monitor-orion.timer` (every 1 minute)
- Timer reliability: `Persistent=true` (missed runs fire after reboot)
- Service: `aegis-monitor-orion.service`
- Script: `/usr/local/bin/aegis-monitor-orion`
  - Repo source: `scripts/aegis_remote/aegis-monitor-orion` (copy to `/usr/local/bin/aegis-monitor-orion` on Hetzner)
- Log: `/var/log/aegis-monitor/monitor.log`

Security sentinel (signal-only):
- Timer: `aegis-sentinel.timer` (every 2 minutes)
- Timer reliability: `Persistent=true` (missed runs fire after reboot)
- Service: `aegis-sentinel.service`
- Script: `/usr/local/bin/aegis-sentinel`
  - Repo source: `scripts/aegis_remote/aegis-sentinel` (copy to `/usr/local/bin/aegis-sentinel` on Hetzner)
- Log: `/var/log/aegis-sentinel/sentinel.log`

Human-in-the-loop defender (allowlisted executor):
- Script: `/usr/local/bin/aegis-defend`
  - Repo source: `scripts/aegis_remote/aegis-defend` (copy to `/usr/local/bin/aegis-defend` on Hetzner)
- Purpose: execute a *tight allowlist* of defensive actions only when ORION (and Cory) explicitly approve.
- Local wrapper (Mac mini / ORION workspace): `scripts/aegis_defense.sh`
Shared alert formatting helper (recommended):
- Script: `/usr/local/bin/lib_alert_format.sh`
  - Repo source: `scripts/aegis_remote/lib_alert_format.sh` (copy next to the AEGIS scripts)

Note: the AEGIS scripts include a small fallback formatter if the helper is missing, but you should deploy the helper to keep alert formatting consistent.

Tailscale:
- Unit: `tailscaled`
- Status: `tailscale status`

## Configuration (Hetzner)

Single env file used by both monitor and sentinel:
- `/etc/aegis-monitor.env` (mode `0640`, group `aegis`)

Required fields:
- `ORION_HOST=` Tailscale IP or hostname of the Mac mini (example `100.112.98.18`)
- `ORION_SSH_USER=` macOS user used for SSH (example `corystoner`)
- `SSH_IDENTITY=` AEGIS private key path on the server

Availability commands (must match the Mac mini forced-command allowlist):
- `ORION_OPENCLAW_HEALTH_CMD="/Users/corystoner/.npm-global/bin/openclaw health"`
- `ORION_OPENCLAW_RESTART_CMD="/Users/corystoner/.npm-global/bin/openclaw gateway restart"`

Slack alerts (primary, optional):
- `SLACK_BOT_TOKEN=...`
- `SLACK_CHANNEL_ID=...`

Telegram alerts (secondary, optional):
- `AEGIS_TELEGRAM_TOKEN=...`
- `AEGIS_TELEGRAM_CHAT_ID=...`

Mini App dashboard (optional but recommended):
- `MINIAPP_INGEST_URL=https://orion-miniapp-cory-95ce0d.fly.dev`
- `MINIAPP_INGEST_TOKEN=...` (must match the Fly `INGEST_TOKEN` secret)

Telegram helper (run on the Hetzner host after you message the bot in the target chat):
- `/usr/local/bin/aegis-telegram-discover-chat`

## Restricted SSH (Mac Mini)

AEGIS uses SSH over Tailscale to run only two operations on the Mac mini:
- `openclaw health`
- `openclaw gateway restart`

Mac mini forced-command script:
- `/Users/corystoner/.openclaw/bin/aegis-ssh-command`

Mac mini key restrictions:
- The AEGIS public key entry in `/Users/corystoner/.ssh/authorized_keys` is restricted by:
  - `from="<AEGIS_TAILSCALE_IP>"`
  - `command="<forced command path>"`
  - `no-pty`, `no-port-forwarding`, etc.

Verification (run from Hetzner as the `aegis` user):
- Allowed:
  - `ssh ... corystoner@<ORION_HOST> 'bash -lc \"/Users/corystoner/.npm-global/bin/openclaw health\"'`
- Blocked:
  - `ssh ... corystoner@<ORION_HOST> 'bash -lc \"whoami\"'`

## Alerts (What You’ll See)

Availability monitor:
- `AEGIS: ORION was unhealthy; restart succeeded.`
- `AEGIS: ORION is unhealthy after restart attempt (INC-AEGIS-...).`
- `AEGIS: ORION recovered.`

Security sentinel:
- `AEGIS: SSH auth anomalies detected (... in ~5m).`
- `AEGIS: fail2ban bans increased (...).`
- `AEGIS: config drift detected on sentinel host. Review system changes.`
- `AEGIS: Tailscale peer status changed. Review tailnet devices.`
- `AEGIS: own OpenClaw service was down; restarted successfully.`
- `AEGIS: own OpenClaw service is down and restart failed.`

Throttling:
- Alerts are throttled to prevent spam loops.
- Typical windows are 10–30 minutes per alert type.
- The Tailscale peer-change alert is intentionally more conservative (currently 60 minutes) to avoid noise from normal device flapping.

## Deploy / Update AEGIS Scripts (Hetzner)

When you change any of the repo files under `scripts/aegis_remote/`, redeploy them to the Hetzner host.

From your local machine (this repo), copy the scripts:

```bash
# Copy scripts (add/remove as needed)
scp scripts/aegis_remote/aegis-monitor-orion \
    scripts/aegis_remote/aegis-sentinel \
    scripts/aegis_remote/aegis-defend \
    scripts/aegis_remote/lib_alert_format.sh \
    root@100.75.104.54:/usr/local/bin/

# Ensure executable bits (remote)
ssh root@100.75.104.54 'chmod 0755 /usr/local/bin/aegis-monitor-orion /usr/local/bin/aegis-sentinel /usr/local/bin/aegis-defend; chmod 0644 /usr/local/bin/lib_alert_format.sh'
```

Restart timers/services (remote):

```bash
ssh root@100.75.104.54 'systemctl restart aegis-monitor-orion.service aegis-sentinel.service'
```

Quick verification (remote):

```bash
ssh root@100.75.104.54 'systemctl --no-pager --full status aegis-monitor-orion.service aegis-sentinel.service | sed -n "1,80p"'
ssh root@100.75.104.54 'tail -n 40 /var/log/aegis-monitor/monitor.log; echo "---"; tail -n 40 /var/log/aegis-sentinel/sentinel.log'
```

Before deploying, run the local reliability gate:

```bash
make ci
```

Optional helper (does the same steps):

```bash
scripts/deploy_aegis_remote.sh
```

## Incident Logging (Auditable History)

AEGIS writes a local, append-only incident history on the Hetzner host:
- Monitor incidents: `/var/lib/aegis-monitor/incidents.md`
- Sentinel incidents: `/var/lib/aegis-sentinel/incidents.md`

The ORION workspace incident log (git-tracked) is:
- `tasks/INCIDENTS.md`

## Defense Plans (HITL)

For security signals, AEGIS can write a defense plan file on the Hetzner host. This is a proposal only; AEGIS does not execute defensive changes automatically.

- Plans directory (Hetzner): `/var/lib/aegis-sentinel/defense_plans/`
- Each plan contains:
  - What happened (why this triggered)
  - Evidence (small, non-secret summary)
  - Suggested allowlisted commands to run via `aegis-defend`
  - Rollback steps
  - An `ApprovalCode` used to ensure each action is explicitly approved

Common flow:
1. AEGIS emits an alert with an `INC-AEGIS-...` incident id.
2. ORION reviews the plan:
   - `scripts/aegis_defense.sh show <INCIDENT_ID>`
3. Cory approves (one-time) or opens a short window (example 30 minutes):
   - One-time: `scripts/aegis_defense.sh run <INCIDENT_ID> <ACTION> --code <ApprovalCode> ...`
   - Window: `scripts/aegis_defense.sh approve <INCIDENT_ID> --minutes 30 --code <ApprovalCode>`
4. ORION executes allowlisted actions only through `aegis-defend`.

## ORION Proactive DM (Optional)

If you want ORION to proactively DM you in Telegram when a new defense plan appears:
- Install the Mac mini LaunchAgent:
  - `scripts/install_orion_aegis_defense_watch_launchagent.sh /Users/corystoner/Desktop/ORION`
- It polls `aegis-defend list` on Hetzner every ~2 minutes and sends a private DM when it sees a new plan.
- To force the DM target chat id, set env var `ORION_TELEGRAM_CHAT_ID` for the LaunchAgent (recommended). Otherwise it will fall back to `AEGIS_TELEGRAM_CHAT_ID` from `/etc/aegis-monitor.env` on Hetzner.

## ORION Restart Loop Guard (Anti-Flap)

AEGIS will attempt to restart ORION when ORION fails health checks, but it includes a **restart-loop guard** to prevent endless restart flapping (bad config, upstream/model outage, etc.).

Defaults (configurable via `/etc/aegis-monitor.env`):
- `AEGIS_ORION_RESTART_MAX=2`
- `AEGIS_ORION_RESTART_WINDOW_SEC=900` (15 minutes)

Tip:
- If you want AEGIS to keep trying longer during extended ORION outages, increase `AEGIS_ORION_RESTART_MAX` (for example `6` or `10`) and/or increase `AEGIS_ORION_RESTART_WINDOW_SEC` to reduce flapping.

Behavior:
- If ORION is unhealthy and AEGIS has already attempted `AEGIS_ORION_RESTART_MAX` restarts inside the window, AEGIS:
  - Creates a guard lock file: `/var/lib/aegis-monitor/orion_restart_guard.lock`
  - Switches to **alert-only** (no more automatic restarts) until the rolling window cools down
  - Automatically clears the lock once enough time passes that the restart-attempt count in the window drops below the limit

Files:
- Restart attempt log: `/var/lib/aegis-monitor/orion_restart_attempts.log`
- Guard lock: `/var/lib/aegis-monitor/orion_restart_guard.lock`

Manual clear (Hetzner, optional):
- `sudo rm -f /var/lib/aegis-monitor/orion_restart_guard.lock`
- Optional (also clear the attempt counter):
  - `sudo rm -f /var/lib/aegis-monitor/orion_restart_attempts.log`

## Log Rotation

AEGIS writes plain log files:
- `/var/log/aegis-monitor/monitor.log`
- `/var/log/aegis-sentinel/sentinel.log`

These should be managed via `logrotate` on the Hetzner host (recommended).

Recommended `logrotate` units (Hetzner):
- `/etc/logrotate.d/aegis-monitor`
- `/etc/logrotate.d/aegis-sentinel`

## Heartbeat / “Is AEGIS Alive?”

AEGIS is designed to be silent when everything is normal, so the canonical “alive” checks are:

Tailscale console:
- Check the device `Last seen` / `Connected` status for the Hetzner host.

On the Hetzner host:
- `systemctl is-active openclaw-aegis.service`
- `systemctl is-active aegis-monitor-orion.timer`
- `systemctl is-active aegis-sentinel.timer`

Quick status summary (Hetzner):
- `/usr/local/bin/aegis-status`
  - Prints systemd status + most recent `last_ok` timestamps + last log lines.

## Operations

Restart components (Hetzner):
- `systemctl restart openclaw-aegis.service`
- `systemctl restart aegis-monitor-orion.timer`
- `systemctl restart aegis-sentinel.timer`

View logs (Hetzner):
- `tail -n 200 /var/log/aegis-monitor/monitor.log`
- `tail -n 200 /var/log/aegis-sentinel/sentinel.log`
- `journalctl -u openclaw-aegis.service -n 200 --no-pager`

Smoke test (controlled):
1. Stop ORION gateway on the Mac mini (locally):
   - `openclaw gateway stop`
2. Wait up to 1–2 minutes.
3. Confirm AEGIS detected it, attempted restart, and ORION is healthy again:
   - Check Slack/Telegram alert
   - Or verify directly: `openclaw health` on the Mac mini

## Security Notes

- Do not commit `/etc/aegis-monitor.env` or any secrets to this repository.
- Treat any bot tokens posted in chat as compromised; rotate them and update `/etc/aegis-monitor.env`.
- Keep AEGIS “alert-only” for security findings. If you want defensive actions later, add a separate approval flow and post-incident review.

## Power Failure / Reboot Behavior (What To Expect)

Power/network failures are a common root cause of “ORION down”.

Expected behavior:
- The systemd timers on Hetzner are `Persistent=true`, so missed runs will fire after the Hetzner host reboots.
- AEGIS can only restart ORION once the Mac mini is reachable over Tailscale SSH and the Mac mini forced-command allowlist is still valid.
- If ORION is unreachable over SSH (host down, network, auth), AEGIS will alert and will not burn restart attempts or trip the restart guard.

If ORION comes back but is still unhealthy:
- AEGIS will attempt `openclaw gateway restart` over restricted SSH.
- If ORION keeps failing health checks after restart attempts, AEGIS will trip the restart guard to prevent flapping (see above).
