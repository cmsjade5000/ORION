# Recovery Verification Probes

Use this checklist after a restart or recovery action to confirm service correctness, not just liveness.

Principles:
- verify in layers (process -> gateway -> channels -> user-visible outcomes)
- keep probes read-only by default
- capture minimal evidence for incidents (no secrets)

## Local (Mac mini) Probes

1. Gateway health:
- `openclaw health`

2. Channel probes:
- `openclaw channels status --probe`

3. Stratus checklist:
- `scripts/stratus_healthcheck.sh`

4. Logs (short excerpt only):
- `openclaw logs --plain --limit 120`

## Remote (AEGIS / Hetzner) Probes

1. AEGIS service health:
- `systemctl status --no-pager openclaw-aegis.service`

2. Sentinel + monitor logs:
- `tail -n 40 /var/log/aegis-monitor/monitor.log`
- `tail -n 40 /var/log/aegis-sentinel/sentinel.log`

## “Recovered” Definition (Minimum)

Mark as recovered only if:
- `openclaw health` is OK
- channel probes are OK (or a known, acknowledged provider outage exists)
- error loops are not repeating in recent logs

If only liveness is restored but probes fail:
- treat as partial recovery
- keep the incident open and escalate to ATLAS/STRATUS with evidence

