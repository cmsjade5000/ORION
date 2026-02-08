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
- Log: `/var/log/aegis-monitor/monitor.log`

Security sentinel (signal-only):
- Timer: `aegis-sentinel.timer` (every 2 minutes)
- Timer reliability: `Persistent=true` (missed runs fire after reboot)
- Service: `aegis-sentinel.service`
- Script: `/usr/local/bin/aegis-sentinel`
- Log: `/var/log/aegis-sentinel/sentinel.log`

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

## Incident Logging (Auditable History)

AEGIS writes a local, append-only incident history on the Hetzner host:
- Monitor incidents: `/var/lib/aegis-monitor/incidents.md`
- Sentinel incidents: `/var/lib/aegis-sentinel/incidents.md`

The ORION workspace incident log (git-tracked) is:
- `tasks/INCIDENTS.md`

## ORION Restart Loop Guard (Anti-Flap)

AEGIS will attempt to restart ORION when ORION fails health checks, but it includes a **restart-loop guard** to prevent endless restart flapping (bad config, upstream/model outage, etc.).

Defaults (configurable via `/etc/aegis-monitor.env`):
- `AEGIS_ORION_RESTART_MAX=2`
- `AEGIS_ORION_RESTART_WINDOW_SEC=900` (15 minutes)

Behavior:
- If ORION is unhealthy and AEGIS has already attempted `AEGIS_ORION_RESTART_MAX` restarts inside the window, AEGIS:
  - Creates a lock file: `/var/lib/aegis-monitor/orion_restart_guard.lock`
  - Switches to **alert-only** (no more automatic restarts) until manual intervention

Files:
- Restart attempt log: `/var/lib/aegis-monitor/orion_restart_attempts.log`
- Guard lock: `/var/lib/aegis-monitor/orion_restart_guard.lock`

Manual clear (Hetzner):
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
