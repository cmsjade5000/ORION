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

## OpenClaw Release Adoption Notes

The AEGIS host was originally onboarded on `2026.1.30`. When upgrading into the
`2026.2.x` and `2026.3.x` line, the changes that materially matter to AEGIS are:

- Explicit heartbeat policy review:
  heartbeat delivery defaults changed across `2026.2.x`, so review the AEGIS
  runtime after upgrade and confirm it still does not perform any unintended
  direct outbound delivery. Do not assume an older heartbeat config key still
  exists unchanged across releases; validate the live schema first.
- Secrets workflow:
  use `openclaw secrets audit` after upgrades and during maintenance checks to
  confirm the host is still using the intended secret file references and that
  migrations did not materialize sensitive values in config.
- Session cleanup:
  prefer first-class `openclaw sessions cleanup ... --dry-run` / `--enforce`
  for deliberate session-store hygiene on the AEGIS host instead of ad hoc file
  deletion.
- Gateway/container health:
  newer OpenClaw releases add built-in `/health`, `/healthz`, `/ready`, and
  `/readyz` endpoints plus stricter gateway/websocket security. These are
  useful for future containerized or proxied AEGIS deployments, even though the
  current Hetzner setup remains loopback-only and systemd-managed.

Detailed release review:
- `docs/AEGIS_OPENCLAW_RELEASE_NOTES_2026_1_30_to_2026_3_13.md`

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

Maintenance monitor (ORION update + security audit; read-only):
- Timer: `aegis-maintenance-orion.timer` (recommended: daily)
- Timer reliability: `Persistent=true` (missed runs fire after reboot)
- Service: `aegis-maintenance-orion.service`
- Script: `/usr/local/bin/aegis-maintenance-orion`
  - Repo source: `scripts/aegis_remote/aegis-maintenance-orion` (copy to `/usr/local/bin/aegis-maintenance-orion` on Hetzner)
- Suggested unit templates (copy to `/etc/systemd/system/`):
  - `docs/systemd/aegis-maintenance-orion.service`
  - `docs/systemd/aegis-maintenance-orion.timer`
- Log: `/var/log/aegis-monitor/maintenance.log`
- Output: writes a HITL plan under:
  - `/var/lib/aegis-sentinel/defense_plans/INC-AEGIS-MAINT-*.md`

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
- `ORION_SSH_STRICT_HOST_KEY_CHECKING=` SSH host-key policy for ORION probes (recommended: `yes`)
- `ORION_SSH_KNOWN_HOSTS=` path to the pinned ORION known-hosts file on the AEGIS host (recommended: `/home/aegis/.ssh/known_hosts`)

Recommended OpenClaw posture on the AEGIS host:
- Keep the runtime aligned with the single-bot policy and verify after upgrades
  that heartbeat/default-delivery behavior has not regressed into direct user
  delivery.

Availability commands (must match the Mac mini forced-command allowlist):
- `ORION_OPENCLAW_HEALTH_CMD="/Users/corystoner/.npm-global/bin/openclaw health"`
- `ORION_OPENCLAW_RESTART_CMD="/Users/corystoner/.npm-global/bin/openclaw gateway restart"`

Slack alerts (primary, optional):
- `SLACK_BOT_TOKEN=...`
- `SLACK_CHANNEL_ID=...`

Telegram alerts (secondary, optional):
- `AEGIS_TELEGRAM_TOKEN=...`
- `AEGIS_TELEGRAM_CHAT_ID=...`

Digesting lower-priority alerts (optional, recommended):
- `AEGIS_DIGEST_ENABLED=1` enables digest mode for configured severities (`0` disables digest mode).
- `AEGIS_DIGEST_SEVERITIES=P2` comma-separated severities to digest (default `P2`).
- `AEGIS_DIGEST_WINDOW_SEC=43200` digest send window in seconds (default 12 hours, approximately twice daily).
- `AEGIS_DIGEST_MAX_ITEMS=25` max events included per digest message before summarizing overflow.

Telegram helper (run on the Hetzner host after you message the bot in the target chat):
- `/usr/local/bin/aegis-telegram-discover-chat`

## Restricted SSH (Mac Mini)

AEGIS uses SSH over Tailscale to run only two operations on the Mac mini:
- `openclaw health`
- `openclaw gateway restart`

Optional read-only maintenance probes (recommended for update monitoring):
- `openclaw security audit --deep --json`
- `openclaw update status` (and/or `openclaw update --json status` if supported)

Mac mini forced-command script:
- `/Users/corystoner/.openclaw/bin/aegis-ssh-command`

Mac mini key restrictions:
- The AEGIS public key entry in `/Users/corystoner/.ssh/authorized_keys` is restricted by:
  - `from="<AEGIS_TAILSCALE_IP>"`
  - `command="<forced command path>"`
  - `no-pty`, `no-port-forwarding`, etc.
- Pin the Mac mini host key in the AEGIS known-hosts file and keep `StrictHostKeyChecking=yes`; avoid `accept-new` for privileged automation.

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
- `AEGIS: ORION is reachable but degraded.`

Security sentinel:
- `AEGIS: SSH auth anomalies detected (... in ~5m).`
- `AEGIS: fail2ban bans increased (...).`
- `AEGIS: config drift detected on sentinel host. Review system changes.`
- `AEGIS: Tailscale peer status changed. Review tailnet devices.`
- `AEGIS: own OpenClaw service was down; restarted successfully.`
- `AEGIS: own OpenClaw service is down and restart failed.`

Digest behavior:
- By default, lower-priority `P2` alerts are queued and sent as a digest every `AEGIS_DIGEST_WINDOW_SEC` (default 12 hours, approximately twice daily).
- `P0/P1` alerts bypass the digest queue and are sent immediately.

Throttling:
- Alerts are throttled to prevent spam loops.
- Typical windows are 10–30 minutes per alert type.
- The Tailscale peer-change alert is intentionally more conservative (currently 60 minutes) to avoid noise from normal device flapping.

## Health Classification

For ORION recovery, treat health as a three-state model:

- `healthy`: gateway service, RPC probe, and config audit are all clean
- `degraded`: gateway is reachable, but RPC/config audit/probe surfaces are not fully clean
- `down`: gateway service or probe path is failing

For local triage on the Mac host, use:

```bash
scripts/stratus_healthcheck.sh
```

This keeps AEGIS and local recovery language aligned with the stricter `2026.3.13` gateway semantics.

## Deploy / Update AEGIS Scripts (Hetzner)

When you change any of the repo files under `scripts/aegis_remote/`, redeploy them to the Hetzner host.

From your local machine (this repo), copy the scripts:

```bash
# Copy scripts (add/remove as needed)
scp scripts/aegis_remote/aegis-monitor-orion \
    scripts/aegis_remote/aegis-maintenance-orion \
    scripts/aegis_remote/aegis-sentinel \
    scripts/aegis_remote/aegis-defend \
    scripts/aegis_remote/lib_alert_format.sh \
    root@100.75.104.54:/usr/local/bin/

# Ensure executable bits (remote)
ssh root@100.75.104.54 'chmod 0755 /usr/local/bin/aegis-monitor-orion /usr/local/bin/aegis-maintenance-orion /usr/local/bin/aegis-sentinel /usr/local/bin/aegis-defend; chmod 0644 /usr/local/bin/lib_alert_format.sh'
```

Restart timers/services (remote):

```bash
ssh root@100.75.104.54 'systemctl restart aegis-monitor-orion.service aegis-sentinel.service'
# If installed:
# ssh root@100.75.104.54 'systemctl restart aegis-maintenance-orion.service'
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

Local ORION wrappers that connect to Hetzner also support pinned-host settings:
- `AEGIS_SSH_STRICT_HOST_KEY_CHECKING=` (recommended: `yes`)
- `AEGIS_SSH_KNOWN_HOSTS=` (recommended: `${HOME}/.ssh/known_hosts` or a dedicated pinned file)

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
  - `scripts/install_orion_aegis_defense_watch_launchagent.sh /Users/corystoner/src/ORION`
- It polls `aegis-defend list` on Hetzner every ~2 minutes and sends a private DM when it sees a new plan.
- To force the DM target chat id, set env var `ORION_TELEGRAM_CHAT_ID` for the LaunchAgent (recommended). Otherwise it will fall back to `AEGIS_TELEGRAM_CHAT_ID` from `/etc/aegis-monitor.env` on Hetzner.
- If Tailscale SSH is gated or unavailable, the watcher writes `tmp/aegis_defense_watch.backoff` and suppresses repeat attempts for `AEGIS_WATCH_REMOTE_FAILURE_BACKOFF_SEC` (default 3600 seconds) so it does not create auth-prompt/log noise every launchd tick.

## ORION Restart Loop Guard (Anti-Flap)

AEGIS will attempt to restart ORION when ORION fails health checks, but it includes a **restart-loop guard** to prevent endless restart flapping (bad config, upstream/model outage, etc.).

Defaults (configurable via `/etc/aegis-monitor.env`):
- `AEGIS_ORION_RESTART_MAX=2`
- `AEGIS_ORION_RESTART_WINDOW_SEC=900` (15 minutes)
- `AEGIS_ORION_CONFIRM_FAILURE_SEC=180` (sustained non-transport health failure required before AEGIS restarts ORION or sends Telegram/Slack)
- `AEGIS_ORION_POST_RESTART_WAIT_SEC=180` (readiness wait after restart before declaring success/failure)
- `AEGIS_ORION_POST_RESTART_POLL_SEC=10`

Tip:
- If you want AEGIS to keep trying longer during extended ORION outages, increase `AEGIS_ORION_RESTART_MAX` (for example `6` or `10`) and/or increase `AEGIS_ORION_RESTART_WINDOW_SEC` to reduce flapping.

Behavior:
- If ORION has a one-off health miss but recovers before `AEGIS_ORION_CONFIRM_FAILURE_SEC`, AEGIS logs it as suspect/transient and stays quiet.
- If ORION is unhealthy after the confirm window and AEGIS has already attempted `AEGIS_ORION_RESTART_MAX` restarts inside the window, AEGIS:
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
- After OpenClaw upgrades, run `openclaw secrets audit` on the AEGIS host and
  verify the runtime still points at the intended secret sources without
  inlining sensitive values.
- After the March 16, 2026 upgrade, do not assume all local loopback probes are
  equivalent. Validate at least:
  - `openclaw health`
  - `openclaw gateway call status --json`
  - `curl -fsS http://127.0.0.1:18889/readyz`
  If they disagree, treat it as an OpenClaw upgrade follow-up and inspect
  `journalctl -u openclaw-aegis.service`.

## Power Failure / Reboot Behavior (What To Expect)

Power/network failures are a common root cause of “ORION down”.

Expected behavior:
- The systemd timers on Hetzner are `Persistent=true`, so missed runs will fire after the Hetzner host reboots.
- AEGIS can only restart ORION once the Mac mini is reachable over Tailscale SSH and the Mac mini forced-command allowlist is still valid.
- If ORION is unreachable over SSH (host down, network, auth), AEGIS will alert and will not burn restart attempts or trip the restart guard.

If ORION comes back but is still unhealthy:
- AEGIS will attempt `openclaw gateway restart` over restricted SSH.
- If ORION keeps failing health checks after restart attempts, AEGIS will trip the restart guard to prevent flapping (see above).
