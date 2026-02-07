# Comprehensive Breakdown of REVIVEBOT Project

> Archived plan (remote AEGIS sentinel). Not part of the current local Mac mini go-live.
> Paths and tooling references may be outdated. AEGIS template lives at `docs/archive/AEGIS/`.

## Phase 0: Progress Updates (in place)
- **Periodic updates** via PULSE cron (`workflows/revivebot-progress.yaml`) to send Telegram notices every 10 minutes during provisioning.

## Phase 1: Hosting Research & Setup

**1.1 Hetzner Cloud (Primary)**
- Confirm compute (CX22/CX32), networking, and storage options.
- Low cost, reliable uptime, simple API-driven provisioning.
- Supports cloud-init for automated setup.

**1.2 Fallback options**
- Identify 2–3 free/low-cost always-on alternatives (Fly.io, Railway, Render).
- Summarize cost, limits (sleeping apps, CPU, bandwidth), complexity, and deployment method.

## Phase 2: Hetzner Provisioning & Quota Prep

**User actions:**
- Sign up for Hetzner Cloud account and add payment method.
- Generate an API token with Read/Write permissions.
- Add public SSH key to the new project.

**Automated steps:**
- Provision compute instance via hcloud CLI or API.
- Configure networking (open port 18789 for WebSocket, HTTP health endpoint).
- Install prerequisites (git, Node.js, systemd).

## Phase 3: ORION Health Endpoint

- Add a `/health` HTTP endpoint returning JSON `{ "status": "ok" }`.
- Implement health logic per definition: reachability, liveness (<5s), freshness (<2m), CPU/disk thresholds.
- Deploy and restart ORION; verify endpoint.

## Phase 4: AEGIS Code & Service Deployment

**4.0 Code Deployment**
- Sync local `docs/archive/AEGIS/` directory to remote `/home/revivebot/aegis` (e.g. `rsync -avz docs/archive/AEGIS/ revivebot@${HOST}:/home/revivebot/aegis`).
- Ensure `index.js` and `package.json` are present.
- Run `npm install` in `/home/revivebot/aegis`.

## Phase 4.1: AEGIS Identity Deployment
- Upload `docs/archive/AEGIS/SOUL.md` to remote host.
- Configure local LLM prompt to respect SOUL directives.
- Ensure Telegram bot identity matches "AEGIS" (User to set name/avatar in BotFather).

**4.1 Monitor service**
- Create a systemd-managed script or binary to continuously check ORION health via HTTP and TCP.
- Implement a state machine: OK → SUSPECT → DOWN → RECOVERING → OK/FAILED.

**4.2 Recovery actions**
- On DOWN: restart ORION (`systemctl restart openclaw-gateway.service`).
- Collect diagnostics: last 200 log lines, journalctl, CPU/memory/disk snapshot, uptime.
- Send a single Telegram alert (30 min cooldown) with a concise summary and diagnostics.

**4.3 Service & logging**
- Deploy REVIVEBOT (AEGIS) as a systemd service on the remote VM:
  - Create `/etc/systemd/system/aegis.service` with the following content:
    ```ini
    [Unit]
    Description=AEGIS Health Monitor
    After=network.target

    [Service]
    User=revivebot
    WorkingDirectory=/home/revivebot/aegis
    ExecStart=/usr/bin/node index.js
    Restart=on-failure
    EnvironmentFile=/home/revivebot/aegis/.env

    [Install]
    WantedBy=multi-user.target
    ```
  - Run `systemctl daemon-reload && systemctl enable aegis && systemctl start aegis`.
- Write structured logs to `~/.revivebot/` for future analysis.

## Phase 5: Testing & Acceptance

1. Stop ORION to simulate failure.
2. Confirm REVIVEBOT detects DOWN after 3 failed checks.
3. Verify one rate-limited Telegram alert.
4. Confirm REVIVEBOT restarts ORION and collects diagnostics.
5. Confirm ORION returns to OK and REVIVEBOT transitions back to OK.

## Phase 6: Runbook, Troubleshooting & Security

**Runbook:** steps to start, stop, and verify REVIVEBOT; viewing logs and state.

**Key rotation:** how to update Telegram tokens and SSH keys in `~/.revivebot/`.

**Troubleshooting:** quick commands for health check, logs, systemd status; escalation steps if REVIVEBOT itself fails.

**Security checklist:** ensure no plaintext secrets, restrict SSH access, enable token-only auth on controlUi.

## Pre-written REVIVEBOT config template

```yaml
revivebot:
  name: "AEGIS"
  version: "0.1"
  timezone: "America/New_York"

  orion:
    health_check:
      method: "http"           # http | tcp | heartbeat
      http:
        url: "https://ORION_PUBLIC_OR_TUNNELED_URL/health"
        timeout_seconds: 5
        expected_status: 200
        expected_body_contains: "ok"  # optional
      tcp:
        host: "89.167.58.238"
        port: 443
        timeout_seconds: 3
      heartbeat:
        max_age_seconds: 120

  thresholds:
    consecutive_failures_to_mark_down: 3
    check_interval_seconds: 60
    jitter_seconds: 10

  recovery:
    enabled: true
    mode: "safe"             # safe | aggressive
    retry:
      max_attempts: 6
      initial_backoff_seconds: 15
      max_backoff_seconds: 300
      backoff_multiplier: 2.0
    cycles:
      max_failed_cycles_before_escalate: 3
    actions:
      - type: "restart_systemd"
        when: "down"
        params:
          ssh:
            host: "ORION_SSH_HOST"
            port: 22
            user: "revivebot"
            key_path: "/etc/revivebot/keys/orion_ed25519"
          service_name: "openclaw-orion"
      - type: "collect_diagnostics"
        when: "down"
        params:
          ssh:
            host: "ORION_SSH_HOST"
            port: 22
            user: "revivebot"
            key_path: "/etc/revivebot/keys/orion_ed25519"
          commands:
            - "uptime"
            - "df -h"
            - "free -h"
            - "journalctl -u openclaw-orion -n 200 --no-pager"
            - "docker logs --tail 200 orion"

  alerts:
    channel: "telegram"       # telegram | webhook | email
    cooldown_seconds: 900
    telegram:
      bot_token: "ENV:AEGIS_TELEGRAM_TOKEN"
      chat_id: "ENV:AEGIS_TELEGRAM_CHAT_ID"

  logging:
    level: "info"
    format: "json"
    file_path: "/var/log/revivebot/revivebot.log"
    rotate:
      max_mb: 25
      backups: 5

  security:
    secrets_strategy: "env"
    allow_remote_restart: true
    ssh:
      strict_host_key_checking: true
      known_hosts_path: "/etc/revivebot/ssh/known_hosts"

  dashboard:
    enabled: false
    bind: "127.0.0.1"
    port: 8787
```
