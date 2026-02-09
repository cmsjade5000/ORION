# Incidents (Audit History)

This repository uses a simple, append-only incident log for **auditable** operational events.

What counts as an incident in this system:
- Any **gateway restart** (ORION or AEGIS).
- Any **security alert** emitted by AEGIS (SSH anomalies, fail2ban spikes, config drift, Tailscale peer changes).
- Any **emergency delegation bypass** (for example ORION directly invoking `NODE`/`PULSE`/`STRATUS` when ATLAS is unavailable).
- Any **ORION unreachable** event (power/network failure, SSH auth breakage, etc.).

## Primary Log (Mac Mini / ORION Workspace)

Append incidents to:
- `tasks/INCIDENTS.md`

## Remote Log (Hetzner / AEGIS Host)

AEGIS appends local incidents on the Hetzner host (not committed to git):
- Monitor incidents: `/var/lib/aegis-monitor/incidents.md`
- Sentinel incidents: `/var/lib/aegis-sentinel/incidents.md`

## Format (INCIDENT v1)

Use this exact format (append-only):

```text
INCIDENT v1
Id: INC-<YYYYMMDD>-<hhmm>-<short> | INC-AEGIS-<YYYYMMDDThhmmssZ>
Opened: <ISO8601 timestamp>
Opened By: ORION | AEGIS
Severity: P0 | P1 | P2
Trigger: <STRING> (examples: ORION_GATEWAY_RESTART, ORION_UNREACHABLE, ORION_RESTART_GUARD, AEGIS_SECURITY_ALERT, ATLAS_UNAVAILABLE)
Summary: <one sentence>
Evidence:
- <short facts only>
Actions:
- <what was done, if anything>
Follow-up Owner: ORION | ATLAS | Cory
Follow-up Tasks:
- <task packet link or short description>
Closed: <ISO8601 timestamp or "open">
```
