# Incidents (Append-Only)

This file is the git-tracked audit log for:
- operational incidents (gateway restarts, “ORION unreachable”, security alerts), and
- emergency events that bypass normal delegation (example: ATLAS unavailable bypass).

Rules:
- Append-only (do not rewrite history).
- Keep entries short and factual (no secrets, no full tool logs, no stack traces).
- Link follow-up work to Task Packets in `tasks/QUEUE.md` and/or `tasks/INBOX/*.md`.
- Prefer using `scripts/incident_append.sh` to reduce formatting drift.

## Incidents

Use this exact format:

```text
INCIDENT v1
Id: INC-<YYYYMMDD>-<hhmm>-<short> | INC-AEGIS-<YYYYMMDDThhmmssZ>
Opened: <ISO8601 timestamp>
Opened By: ORION | AEGIS
Severity: P0 | P1 | P2
Trigger: <STRING>  (examples: ORION_GATEWAY_RESTART, ORION_UNREACHABLE, AEGIS_SECURITY_ALERT, ATLAS_UNAVAILABLE)
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

INCIDENT v1
Id: INC-20260316-0621-orion-recurring-erro
Opened: 2026-03-16T06:21:24Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260316-0621-orion-recurring-erro
Opened: 2026-03-16T06:21:24Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260316-0621-orion-recurring-erro
Opened: 2026-03-16T06:21:24Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=1528aae4c8cc59a5 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260316-0621-orion-recurring-erro
Opened: 2026-03-16T06:21:24Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=43e262afee0f1b4e occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260316-1421-aegis-hardening
Opened: 2026-03-16T14:27:43Z
Opened By: ORION
Severity: P1
Trigger: AEGIS_SECURITY_ALERT
Summary: Expected AEGIS drift after hardening, strict SSH pinning, and maintenance timer enablement.
Evidence:
- Remote incident INC-AEGIS-SEC-20260316T142119Z was triggered immediately after AEGIS script/env updates.
- Hetzner verification showed strict SSH pinning active and aegis-maintenance-orion.timer enabled.
Actions:
- Deployed patched AEGIS scripts to 100.75.104.54 and backed up prior remote copies.
- Pinned ORION ED25519 host key in /home/aegis/.ssh/known_hosts and set strict SSH vars in /etc/aegis-monitor.env.
- Installed and validated aegis-maintenance-orion.service/timer; final maintenance run exited 0 with no actionable findings.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Optional: clear or annotate the expected remote drift incident after review.
- Plan OpenClaw runtime update on AEGIS host (current v2026.1.30, update available v2026.3.2).
Closed: open

INCIDENT v1
Id: INC-20260316-1505-aegis-openclaw-upgrade
Opened: 2026-03-16T15:05:45Z
Opened By: ORION
Severity: P1
Trigger: AEGIS_SECURITY_ALERT
Summary: AEGIS was upgraded to OpenClaw 2026.3.13, but post-upgrade loopback probe behavior remains inconsistent.
Evidence:
- Host runtime was upgraded from 2026.1.30 to 2026.3.13.
- `openclaw gateway call status --json` and `openclaw health` exposed scope and loopback-probe regressions during validation.
- Direct token-cleanup migration to env-only config was not safe to keep enabled on the live host.
Actions:
- Reviewed all AEGIS-relevant upstream releases between 2026.1.30 and 2026.3.13.
- Restored the host to a known-good config shape after the env-only token experiment caused restart churn.
- Added release-adoption and post-upgrade verification notes to the repo runbooks.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Revisit the AEGIS host loopback probe path after the next OpenClaw patch release.
- If probe drift persists, capture a minimal upstream repro for loopback auth/probe inconsistency on the Hetzner host.
Closed: open
