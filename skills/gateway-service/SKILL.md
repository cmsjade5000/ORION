---
name: gateway-service
description: Install/start/stop/status/log-tail the OpenClaw gateway service (LaunchAgent) for reliable cron/heartbeat execution.
metadata:
  invocation: user
---

# Gateway Service Manager (macOS)

Cron + heartbeat reliability depends on the gateway running persistently.

## Status

```bash
openclaw gateway status
```

## Install Service (LaunchAgent)

```bash
openclaw gateway install
```

## Start / Stop / Restart

```bash
openclaw gateway start
openclaw gateway stop
openclaw gateway restart
```

## Logs

OpenClaw typically logs to:

```bash
ls -la /tmp/openclaw/
tail -n 200 /tmp/openclaw/openclaw-*.log
```

## Hard Rule

Do not switch `gateway.bind` off loopback without explicit confirmation.
