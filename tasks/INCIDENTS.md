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

INCIDENT v1
Id: INC-20260328-0618-orion-recurring-erro
Opened: 2026-03-28T06:18:56Z
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
Id: INC-20260328-0618-orion-recurring-erro
Opened: 2026-03-28T06:18:56Z
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
Id: INC-20260402-1311-orion-recurring-erro
Opened: 2026-04-02T13:11:39Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260402-1311-orion-recurring-erro
Opened: 2026-04-02T13:11:39Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:04Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:04Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t01:40:16.440-04:00 [agent/embedded] embedded run agent end: runid=8056c5b8-ef01-4117-873c-16e4fa80becf iserro
Evidence:
- fingerprint=8d8237e0557d5762 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t01:55:06.093-04:00 [agent/embedded] embedded run agent end: runid=abecb5a4-8b80-4d30-b4fe-4d35e7966f48 iserro
Evidence:
- fingerprint=a60aa74f1a09bbd1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:00:34.899-04:00 [agent/embedded] embedded run agent end: runid=93d26f72-f329-4fa4-963b-9f8d1b6ee5f7 iserro
Evidence:
- fingerprint=3c11b9c9af02a6bf occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:02:07.498-04:00 [agent/embedded] embedded run agent end: runid=48c9af6e-e493-476a-9fee-84df36177f81 iserro
Evidence:
- fingerprint=8456abfa79019147 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:12:11.031-04:00 [agent/embedded] embedded run agent end: runid=ee4015d2-24a4-4fa9-abf2-13791fa0f8b7 iserro
Evidence:
- fingerprint=f667aed8862a5b46 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:36:06.244-04:00 [agent/embedded] embedded run agent end: runid=e88b0690-148b-4a4c-bf1d-d00941567565 iserro
Evidence:
- fingerprint=401cf7fcbc5f2fc7 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:40:26.825-04:00 [agent/embedded] embedded run agent end: runid=585e58ac-6708-4bb7-95ac-97fa695cbf12 iserro
Evidence:
- fingerprint=f84226b3faa84bf9 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:45:56.369-04:00 [agent/embedded] embedded run agent end: runid=bb5488af-1a2e-4746-8391-f91732e2f685 iserro
Evidence:
- fingerprint=0f3b2ba1bd764956 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:50:30.265-04:00 [agent/embedded] embedded run agent end: runid=3e90444f-e0bf-4fe8-b744-61f8cdd4efbf iserro
Evidence:
- fingerprint=a5555c8c00b91d7c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t02:52:07.465-04:00 [agent/embedded] embedded run agent end: runid=3bd334b2-5ab7-4b45-9dbd-869f33e62350 iserro
Evidence:
- fingerprint=318250fe01d140ff occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:00:21.619-04:00 [agent/embedded] embedded run agent end: runid=428dac05-6188-4856-b2ea-be2b823a0b9b iserro
Evidence:
- fingerprint=9890bd92efa3b4b9 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:05:06.607-04:00 [agent/embedded] embedded run agent end: runid=458ae34b-8a79-450c-89b0-36dbb6178846 iserro
Evidence:
- fingerprint=2dad43d16a0169c9 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:18:09.914-04:00 [agent/embedded] embedded run agent end: runid=1761516d-d40f-4581-82f3-5aad3f152424 iserro
Evidence:
- fingerprint=06bf998309c432fe occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:28:08.027-04:00 [agent/embedded] embedded run agent end: runid=6a30962b-441c-4be9-aaab-ace377408b3b iserro
Evidence:
- fingerprint=9fa737ed85551abf occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:30:26.461-04:00 [agent/embedded] embedded run agent end: runid=2f1a23df-d322-4279-b80d-be1a6d1120b9 iserro
Evidence:
- fingerprint=a6bc2573738a8516 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:38:08.402-04:00 [agent/embedded] embedded run agent end: runid=ef1c0473-372e-4942-a471-d2a8ee17e5c5 iserro
Evidence:
- fingerprint=8c60c7cf7b5cf625 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:40:06.556-04:00 [agent/embedded] embedded run agent end: runid=14880db7-9f8b-4737-91bd-895c4c546dc1 iserro
Evidence:
- fingerprint=3c3e47d42d7a17e6 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:42:06.348-04:00 [agent/embedded] embedded run agent end: runid=f5151614-14cf-40c9-89a1-bce197db4301 iserro
Evidence:
- fingerprint=69ab9f9f3a6370dc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t03:50:30.640-04:00 [agent/embedded] embedded run agent end: runid=c7c890af-ff25-47f9-9bfc-0fb8ba40ecee iserro
Evidence:
- fingerprint=02337c4966eb5fce occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:00:55.028-04:00 [agent/embedded] embedded run agent end: runid=a4db8692-1257-445f-a742-4edd8d5365b2 iserro
Evidence:
- fingerprint=d7fb3093dc3c5bbd occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:12:07.841-04:00 [agent/embedded] embedded run agent end: runid=45f54837-0120-4fbe-9c5e-ba84502645ce iserro
Evidence:
- fingerprint=77f1ac87579b59cb occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:22:09.010-04:00 [agent/embedded] embedded run agent end: runid=45dd827f-485b-46cc-8b67-5bdffec6c7e2 iserro
Evidence:
- fingerprint=cee2c6f9679b33b0 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:24:30.976-04:00 [agent/embedded] embedded run agent end: runid=cc909e89-2fd2-424e-ad7b-33b8fe075167 iserro
Evidence:
- fingerprint=4541e351934a887b occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:26:07.393-04:00 [agent/embedded] embedded run agent end: runid=db3da21a-2d93-4071-8acd-908d457409f4 iserro
Evidence:
- fingerprint=27a84fd46a03459c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:35:07.691-04:00 [agent/embedded] embedded run agent end: runid=7b89581d-1c73-4910-9bea-bb2bf498c1ae iserro
Evidence:
- fingerprint=6f7666227731e21a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:43Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:42:12.532-04:00 [agent/embedded] embedded run agent end: runid=dd450a52-5cb3-40a5-8689-b8e3f1c590c6 iserro
Evidence:
- fingerprint=3438a9685b04ea85 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:45:07.532-04:00 [agent/embedded] embedded run agent end: runid=a14258e6-ffc9-4c34-acad-755256092cd0 iserro
Evidence:
- fingerprint=212c673481a8e548 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:55:07.583-04:00 [agent/embedded] embedded run agent end: runid=a35cf515-0c59-4e9d-bd18-d5105acaba29 iserro
Evidence:
- fingerprint=c77e54e30c02181d occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t04:56:07.534-04:00 [agent/embedded] embedded run agent end: runid=ae82b70a-200e-46e0-ad8d-ff1ba6938e25 iserro
Evidence:
- fingerprint=5128814b2032124b occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t05:15:06.109-04:00 [agent/embedded] embedded run agent end: runid=f862871b-d34c-45ad-b418-ba3161efe02a iserro
Evidence:
- fingerprint=0f0b234131613812 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t05:24:34.894-04:00 [agent/embedded] embedded run agent end: runid=bd45ae93-625d-4866-a058-5949da8a745c iserro
Evidence:
- fingerprint=f5c1cea7150eeecc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t05:26:10.149-04:00 [agent/embedded] embedded run agent end: runid=988439ac-c2c6-473b-9003-edc65fcd5ada iserro
Evidence:
- fingerprint=2bde5ed0707493f5 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t05:36:07.893-04:00 [agent/embedded] embedded run agent end: runid=6b279b94-624f-4ffb-a531-90169fc5984a iserro
Evidence:
- fingerprint=dfcf671de31891cc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t05:40:06.554-04:00 [agent/embedded] embedded run agent end: runid=a8182401-bb52-45e8-ae42-41cf3dc40f6b iserro
Evidence:
- fingerprint=1aa3d630b4da8931 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:00:31.948-04:00 [agent/embedded] embedded run agent end: runid=3d4e7489-1d8e-4ad1-8220-95cc0044674b iserro
Evidence:
- fingerprint=28e8ce2b26bd2b82 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:05:26.422-04:00 [agent/embedded] embedded run agent end: runid=52a04954-67c4-4faf-8492-05d198e00d4e iserro
Evidence:
- fingerprint=9bf4d6dbf8cc62a8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:10:05.565-04:00 [agent/embedded] embedded run agent end: runid=5bf480ca-e0d2-4fb7-bc3f-280e4d25fb9e iserro
Evidence:
- fingerprint=8de2ed6f0d1bce14 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:15:24.127-04:00 [agent/embedded] embedded run agent end: runid=4cd522c3-b955-46b7-9cb2-9b20c392c3aa iserro
Evidence:
- fingerprint=c446f797031fc92f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:22:06.754-04:00 [agent/embedded] embedded run agent end: runid=2a2d3ba3-513f-42b7-9103-ee11b5efbd4f iserro
Evidence:
- fingerprint=89564c4408b4227b occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:25:09.774-04:00 [agent/embedded] embedded run agent end: runid=924ce630-2c45-49d8-bb02-2ef256653eaf iserro
Evidence:
- fingerprint=f98c846d8f21eb4c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:30:52.226-04:00 [agent/embedded] embedded run agent end: runid=7844eb94-21fb-49d8-9457-e3a2173a7660 iserro
Evidence:
- fingerprint=5f0465adb0f45c44 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:36:07.463-04:00 [agent/embedded] embedded run agent end: runid=3c3aa0fc-87ec-4d1b-b2b5-0fc93e33da69 iserro
Evidence:
- fingerprint=d9ea528f9a3ce157 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:38:06.048-04:00 [agent/embedded] embedded run agent end: runid=01d92955-57ad-4747-827a-2d319c567dc5 iserro
Evidence:
- fingerprint=4e86f2b0d56e314a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t06:52:06.191-04:00 [agent/embedded] embedded run agent end: runid=c364587d-edf0-42a9-9e3d-073abcdc3bc4 iserro
Evidence:
- fingerprint=2966b6f0b7610365 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:05:07.180-04:00 [agent/embedded] embedded run agent end: runid=c4b846f6-c1d2-42dd-bc1e-179ba40770bc iserro
Evidence:
- fingerprint=c70fe4071dbf2ea5 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:12:13.175-04:00 [agent/embedded] embedded run agent end: runid=3b946a86-1187-46a2-b06d-14838c228d2e iserro
Evidence:
- fingerprint=a94ec5d67e459846 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:18:06.809-04:00 [agent/embedded] embedded run agent end: runid=1cba4733-9ea6-4a2c-8fc9-ce09aa607b11 iserro
Evidence:
- fingerprint=c5090f9bdacbabaa occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:20:33.682-04:00 [agent/embedded] embedded run agent end: runid=ac4ac309-7ff9-44c0-b44a-60022a1f932a iserro
Evidence:
- fingerprint=490742983e445df5 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:25:05.642-04:00 [agent/embedded] embedded run agent end: runid=0e27abd3-4509-41ab-9b9f-f4893e85c5c2 iserro
Evidence:
- fingerprint=9866bb4c14f4a6a8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:30:06.071-04:00 [agent/embedded] embedded run agent end: runid=4c6c0a43-184c-41e7-a560-bfd7ed7d3885 iserro
Evidence:
- fingerprint=04b3a3781bcbe3c8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:40:07.891-04:00 [agent/embedded] embedded run agent end: runid=be678390-23cd-473b-b484-2fe51607d7d2 iserro
Evidence:
- fingerprint=440ca4562b24ee01 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t07:50:31.985-04:00 [agent/embedded] embedded run agent end: runid=f7386fc5-a2be-4367-b3fe-7335c9fedbfa iserro
Evidence:
- fingerprint=fed09bd844b6a690 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:08:07.300-04:00 [agent/embedded] embedded run agent end: runid=7f1a73ce-bca3-4ef2-bc94-27d0c816cc96 iserro
Evidence:
- fingerprint=c682ca5960108756 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:18:10.167-04:00 [agent/embedded] embedded run agent end: runid=0c9aede5-49cd-483b-a069-98fd1f6e6c79 iserro
Evidence:
- fingerprint=4dad33eb056d4c71 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:26:07.740-04:00 [agent/embedded] embedded run agent end: runid=77323f2f-d395-44e5-a15c-e2caa95bacd2 iserro
Evidence:
- fingerprint=57171150446a64bd occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:44:41.015-04:00 [agent/embedded] embedded run agent end: runid=bee27c68-2fad-411d-bf5a-11330fc3d06b iserro
Evidence:
- fingerprint=6de534717a1eb663 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:46:08.418-04:00 [agent/embedded] embedded run agent end: runid=146ea4c4-54fb-41f2-aef0-02c0e08921ec iserro
Evidence:
- fingerprint=3144899b75f7e093 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:50:47.409-04:00 [agent/embedded] embedded run agent end: runid=733ccbdc-dc3f-4c29-8074-61ceba3cb209 iserro
Evidence:
- fingerprint=ae108c358fc8c50e occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t08:54:19.669-04:00 [agent/embedded] embedded run agent end: runid=790b541f-4146-42b3-80e9-5f42cfdffe6e iserro
Evidence:
- fingerprint=99bf37652e1fcaa1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-02t09:08:10.818-04:00 [agent/embedded] embedded run agent end: runid=9f00a589-d0c4-45a6-a8f0-fcf2d05cb972 iserro
Evidence:
- fingerprint=cae5386037973fb7 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260403-0615-orion-recurring-erro
Opened: 2026-04-03T06:15:44Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:21.360-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=3daf49e432d0a2ee occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:23.397-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=937e17351951bdce occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:27.429-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=0fdd8350a91a6727 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:35.459-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=185a5d4d7125e81a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:35.472-04:00 [diagnostic] lane task error: lane=main durationms=14426 error="failovererror: llm request
Evidence:
- fingerprint=0925deb323c92e67 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:37.314-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=febf395e61e42098 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:40.925-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=48bb618786d77394 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:46.348-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=742497d4b3aadb56 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:55.775-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=c9e4a4433e37090f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:55.797-04:00 [diagnostic] lane task error: lane=main durationms=20322 error="failovererror: llm request
Evidence:
- fingerprint=89a239774d7cc6b1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:12:57.068-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=b189e753d9f73bc8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:00.343-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=d10b939f7bd94900 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:05.616-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=dcb4fec89ec56c55 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:15.086-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=44a6f0c93e2f2f1a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:15.112-04:00 [diagnostic] lane task error: lane=main durationms=19312 error="failovererror: llm request
Evidence:
- fingerprint=b18a6fc7e28619fa occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:15.182-04:00 [diagnostic] lane task error: lane=main durationms=67 error="failovererror: unknown model:
Evidence:
- fingerprint=10d6f74896c32d8e occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:16.684-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=ed52c9b9bf56e571 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:20.186-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=68c96f202f248902 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:26.100-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=88e3ad66a915d3ba occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:10Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:36.205-04:00 [agent/embedded] embedded run agent end: runid=977bf5e2-400c-4e6f-8a2d-9e80ce5da218 iserro
Evidence:
- fingerprint=ddacfae6c3569290 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:11Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-03t11:13:36.474-04:00 [diagnostic] lane task error: lane=main durationms=21290 error="failovererror: llm request
Evidence:
- fingerprint=a95540862435f5d0 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:11Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:11Z
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
Id: INC-20260405-0615-orion-recurring-erro
Opened: 2026-04-05T06:15:11Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: telegram
Evidence:
- fingerprint=d3befd85c8815890 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260407-0615-orion-recurring-erro
Opened: 2026-04-07T06:15:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260407-0616-orion-recurring-erro
Opened: 2026-04-07T06:16:06Z
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
Id: INC-20260407-0616-orion-recurring-erro
Opened: 2026-04-07T06:16:06Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260407-0616-orion-recurring-erro
Opened: 2026-04-07T06:16:06Z
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
Id: INC-20260408-0036-orion-recurring-erro
Opened: 2026-04-08T00:36:21Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0036-orion-recurring-erro
Opened: 2026-04-08T00:36:21Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=61200bd1e10266dc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0036-orion-recurring-erro
Opened: 2026-04-08T00:36:21Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0036-orion-recurring-erro
Opened: 2026-04-08T00:36:21Z
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
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=6
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=61200bd1e10266dc occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=ced5728bc4e1aa40 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
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
Id: INC-20260408-0058-orion-recurring-erro
Opened: 2026-04-08T00:58:52Z
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
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=7
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=7
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=5
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=43e262afee0f1b4e occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=ced5728bc4e1aa40 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=61200bd1e10266dc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=a832172ee42a60f8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=7a9ce8f026008d9b occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9aba6c7496b18c83 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9d773f08ffb81389 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=63cdb82a85455795 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:30:54.628-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=548a414a406e517c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=ffdfe7eef1b30c7c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0615-orion-recurring-erro
Opened: 2026-04-08T06:15:56Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=72df664347580620 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=10
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=10
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=6c8e4a29f5376463 occurrences=5
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=5
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=43e262afee0f1b4e occurrences=5
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=a832172ee42a60f8 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=7a9ce8f026008d9b occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9aba6c7496b18c83 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9d773f08ffb81389 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=63cdb82a85455795 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:30:54.628-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=548a414a406e517c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=ffdfe7eef1b30c7c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=72df664347580620 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=ced5728bc4e1aa40 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=922f33a9aa609c04 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=61200bd1e10266dc occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:35:37.437-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=da8a7013603cf452 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:05.879-04:00 [agent] embedded run agent end: runid=23af1fc5-84c7-4610-9503-c151740701d7 iserror=true mo
Evidence:
- fingerprint=9b505e28b30611e0 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:05.954-04:00 [diagnostic] lane task error: lane=main durationms=207720 error="failovererror: ⚠️ you exc
Evidence:
- fingerprint=1df7f330202827e2 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:39.443-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=3869557b61deec22 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260408-0616-orion-recurring-erro
Opened: 2026-04-08T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:45:43.954-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=87fb35a0b0c91c0a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=8
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=8
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=43e262afee0f1b4e occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=922f33a9aa609c04 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=a832172ee42a60f8 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=7a9ce8f026008d9b occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9aba6c7496b18c83 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=9d773f08ffb81389 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=63cdb82a85455795 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:30:54.628-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=548a414a406e517c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:35:37.437-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=da8a7013603cf452 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:05.879-04:00 [agent] embedded run agent end: runid=23af1fc5-84c7-4610-9503-c151740701d7 iserror=true mo
Evidence:
- fingerprint=9b505e28b30611e0 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:41Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:05.954-04:00 [diagnostic] lane task error: lane=main durationms=207720 error="failovererror: ⚠️ you exc
Evidence:
- fingerprint=1df7f330202827e2 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:40:39.443-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=3869557b61deec22 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:45:43.954-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=87fb35a0b0c91c0a occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=ffdfe7eef1b30c7c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=8484e5f3d4cf671f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=72df664347580620 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=95bd0ca5fb8daea2 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=cff8764d8b7d8298 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0052-orion-recurring-erro
Opened: 2026-04-09T00:52:42Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=96d4ba9217749d5f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=7
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=6
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=8484e5f3d4cf671f occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=95bd0ca5fb8daea2 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=cff8764d8b7d8298 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=922f33a9aa609c04 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=8deb3c90605efba1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=bdde1c05e11c3bd2 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=97705256e05d1220 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=e4a12ace9c487b2e occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=6307238cfa115d7d occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:30:54.628-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=baa6636c808d76f1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=ffdfe7eef1b30c7c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=72df664347580620 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0615-orion-recurring-erro
Opened: 2026-04-09T06:15:34Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=96d4ba9217749d5f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=4e165eeb63e1064f occurrences=8
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=8
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=7f6075bef459ba97 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: gateway
Evidence:
- fingerprint=8484e5f3d4cf671f occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: session
Evidence:
- fingerprint=95bd0ca5fb8daea2 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=cff8764d8b7d8298 occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
Evidence:
- fingerprint=922f33a9aa609c04 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=8deb3c90605efba1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=bdde1c05e11c3bd2 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=97705256e05d1220 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=e4a12ace9c487b2e occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=6307238cfa115d7d occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: 2026-04-07t20:30:54.628-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
Evidence:
- fingerprint=baa6636c808d76f1 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: config
Evidence:
- fingerprint=ffdfe7eef1b30c7c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: plugin
Evidence:
- fingerprint=72df664347580620 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260409-0616-orion-recurring-erro
Opened: 2026-04-09T06:16:01Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: {"0":"[openclaw] unhandled promise rejection: error: agent listener invoked outside active run\n at agent.processevents
Evidence:
- fingerprint=96d4ba9217749d5f occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260410-0615-orion-recurring-erro
Opened: 2026-04-10T06:15:52Z
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
Id: INC-20260410-0615-orion-recurring-erro
Opened: 2026-04-10T06:15:52Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260410-0618-orion-recurring-erro
Opened: 2026-04-10T06:18:08Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260410-0618-orion-recurring-erro
Opened: 2026-04-10T06:18:09Z
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
Id: INC-20260411-0615-orion-recurring-erro
Opened: 2026-04-11T06:15:23Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=5
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260411-0615-orion-recurring-erro
Opened: 2026-04-11T06:15:23Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: discord
Evidence:
- fingerprint=87e4e8d9dfae6494 occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260411-0615-orion-recurring-erro
Opened: 2026-04-11T06:15:23Z
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
Id: INC-20260411-0619-orion-recurring-erro
Opened: 2026-04-11T06:19:39Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=3
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260412-0617-orion-recurring-erro
Opened: 2026-04-12T06:17:15Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=6
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open

INCIDENT v1
Id: INC-20260413-0616-orion-recurring-erro
Opened: 2026-04-13T06:16:31Z
Opened By: ORION
Severity: P1
Trigger: ORION_RECURRING_ERROR
Summary: timeout
Evidence:
- fingerprint=06d03c2a3d62411c occurrences=4
Actions:
- Nightly ORION error review escalated the recurring error.
Follow-up Owner: ATLAS
Follow-up Tasks:
- Review recurring runtime error and harden the prevention path.
Closed: open
