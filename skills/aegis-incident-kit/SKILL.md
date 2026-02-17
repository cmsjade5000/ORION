---
name: aegis-incident-kit
description: Generate an AEGIS incident severity classification and HITL defense/recovery plan from a bundle of signals (deterministic, no network).
metadata:
  invocation: user
---

# AEGIS Incident Kit

Use this skill to turn raw sentinel signals into a consistent incident plan artifact.

## Input (JSON)

Example:

```json
{
  "incident_id": "INC-AEGIS-20260217T154500Z",
  "detected_utc": "2026-02-17T15:45:00Z",
  "gateway_health_ok": false,
  "gateway_health_note": "openclaw health failed",
  "restarts_15m": 3,
  "ssh_auth_failures_15m": 0,
  "fail2ban_bans_15m": 0,
  "tailscale_peers_changed": false,
  "config_integrity_ok": true,
  "config_changed_files": [],
  "user_reports": true
}
```

## Generate Plan

```bash
python3 scripts/aegis_incident_score.py --input signals.json
```

Output is `AEGIS_PLAN v1` with:
- Severity (S1..S4)
- Reasons + Evidence (short, safe)
- Recommended allowlisted actions (proposal only)
- Rollback notes + verification probes

## Recovery Verification

Use the probe list in:
- `docs/RECOVERY_VERIFICATION.md`

