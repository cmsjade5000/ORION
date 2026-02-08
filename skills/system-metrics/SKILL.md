---
name: system-metrics
description: Quick, low-risk system/resource diagnostics for ATLAS/STRATUS/PULSE (CPU/mem/disk/processes) plus OpenClaw health checks using repo scripts.
metadata:
  invocation: user
  openclaw:
    emoji: "🩺"
---

# System Metrics (ATLAS / STRATUS / PULSE)

Use this skill when you need:
- basic host resource checks (CPU/memory/disk)
- OpenClaw gateway diagnostics
- fast triage output that is safe to paste into a Task Packet

## Safe Defaults

- Read-only: do not kill processes or restart services unless explicitly directed by ORION/Cory.
- Redact secrets: never paste tokens, keys, or full config dumps.
- Prefer existing scripts:
  - `status.sh`
  - `scripts/diagnose_gateway.sh`
  - `scripts/fs_audit.sh`

## Local (Mac Mini) Quick Triage

```bash
./status.sh
./scripts/diagnose_gateway.sh
./scripts/fs_audit.sh
```

If you need more detail:

```bash
uptime
df -h /
ps aux | egrep 'openclaw|node' | head
```

## Remote (AEGIS / Linux) Quick Triage

```bash
systemctl status --no-pager openclaw-aegis.service
systemctl list-timers --no-pager | egrep 'aegis-(monitor|sentinel)' || true
tail -n 40 /var/log/aegis-monitor/monitor.log
tail -n 40 /var/log/aegis-sentinel/sentinel.log
```

## Output Format (For Task Packets)

Return a short, factual checklist:

```text
CHECKS:
- gateway health: OK|FAIL
- channels: telegram OK, slack OK
- host resources: load=<...> disk=<...> mem_free=<...>
- logs: <1-3 notable lines>
NEXT:
- <1 recommended next step>
```

