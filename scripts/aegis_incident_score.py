#!/usr/bin/env python3
"""
AEGIS incident correlation + severity classification + HITL defense plan generator.

This is a local deterministic helper that converts a bundle of signals into:
- severity (S1..S4)
- a short evidence summary
- recommended allowlisted actions (proposal only)
- rollback notes and verification probes

It does not perform any remote actions and should not include secrets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SEVERITIES = ("S1", "S2", "S3", "S4")


@dataclass(frozen=True)
class Score:
    severity: str
    reasons: list[str]
    evidence: list[str]
    recommended_actions: list[str]
    rollback: list[str]
    verification_probes: list[str]


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bool(obj: dict[str, Any], key: str, default: bool = False) -> bool:
    v = obj.get(key, default)
    return bool(v)


def _int(obj: dict[str, Any], key: str, default: int = 0) -> int:
    v = obj.get(key, default)
    try:
        return int(v)
    except Exception:
        return default


def _list_str(obj: dict[str, Any], key: str) -> list[str]:
    v = obj.get(key, [])
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for it in v:
        s = str(it).strip()
        if s:
            out.append(s)
    return out


def score_signals(sig: dict[str, Any]) -> Score:
    """
    Expected input JSON keys (all optional):
    - incident_id (string)
    - gateway_health_ok (bool)
    - gateway_health_note (string)
    - restarts_15m (int)
    - ssh_auth_failures_15m (int)
    - fail2ban_bans_15m (int)
    - tailscale_peers_changed (bool)
    - config_integrity_ok (bool)
    - config_changed_files (list[str])
    - user_reports (bool)
    """
    gateway_ok = _bool(sig, "gateway_health_ok", True)
    restarts = _int(sig, "restarts_15m", 0)
    ssh_fail = _int(sig, "ssh_auth_failures_15m", 0)
    bans = _int(sig, "fail2ban_bans_15m", 0)
    peers_changed = _bool(sig, "tailscale_peers_changed", False)
    cfg_ok = _bool(sig, "config_integrity_ok", True)
    cfg_files = _list_str(sig, "config_changed_files")
    user_reports = _bool(sig, "user_reports", False)
    note = str(sig.get("gateway_health_note", "")).strip()

    reasons: list[str] = []
    evidence: list[str] = []

    if not gateway_ok:
        reasons.append("gateway health check failing")
        evidence.append("gateway_health_ok=false" + (f" ({note})" if note else ""))
    if restarts >= 3:
        reasons.append("gateway restart flapping (>=3 in 15m)")
        evidence.append(f"restarts_15m={restarts}")
    elif restarts > 0:
        evidence.append(f"restarts_15m={restarts}")

    if not cfg_ok:
        reasons.append("config integrity check failed")
        evidence.append("config_integrity_ok=false")
        if cfg_files:
            evidence.append("config_changed_files=" + ", ".join(cfg_files[:8]))

    if ssh_fail >= 30:
        reasons.append("high SSH auth failures (>=30 in 15m)")
        evidence.append(f"ssh_auth_failures_15m={ssh_fail}")
    elif ssh_fail > 0:
        evidence.append(f"ssh_auth_failures_15m={ssh_fail}")

    if bans >= 10:
        reasons.append("fail2ban ban spike (>=10 in 15m)")
        evidence.append(f"fail2ban_bans_15m={bans}")
    elif bans > 0:
        evidence.append(f"fail2ban_bans_15m={bans}")

    if peers_changed:
        evidence.append("tailscale_peers_changed=true")
        if gateway_ok and cfg_ok:
            reasons.append("unexpected tailscale peer changes")

    if user_reports:
        reasons.append("user-reported impact")
        evidence.append("user_reports=true")

    # Severity rubric (highest wins):
    # S1: probable compromise/drift or outage
    # S2: urgent reliability/security anomaly (needs prompt attention)
    # S3: notable but not urgent (monitor + batch)
    # S4: informational
    severity = "S4"
    if (not gateway_ok) or (not cfg_ok) or ssh_fail >= 100:
        severity = "S1"
    elif restarts >= 3 or ssh_fail >= 30 or bans >= 10 or user_reports:
        severity = "S2"
    elif restarts > 0 or ssh_fail > 0 or bans > 0 or peers_changed:
        severity = "S3"

    recommended_actions: list[str] = []
    rollback: list[str] = []
    probes: list[str] = [
        "openclaw health",
        "openclaw channels status --probe",
        "scripts/stratus_healthcheck.sh",
    ]

    # Propose allowlisted actions only; execution is human-in-the-loop.
    if not gateway_ok:
        recommended_actions.append("Attempt allowlisted recovery: openclaw gateway restart (if flapping guard permits).")
        rollback.append("If restart worsens behavior, stop and collect logs; do not loop restarts blindly.")
    if not cfg_ok:
        recommended_actions.append("Treat as alert-only: review changed files and recent deploys; do not auto-remediate.")
        rollback.append("If a config rollback is considered, require explicit approval and a verification plan.")
    if ssh_fail >= 30 or bans >= 10:
        recommended_actions.append("Alert-only: gather minimal evidence (counts + timestamps) and prepare HITL defense plan.")
        rollback.append("Do not change firewall/keys automatically; keep posture unchanged until approved.")

    if not recommended_actions:
        recommended_actions.append("No action required; continue monitoring.")
        rollback.append("None.")

    return Score(
        severity=severity,
        reasons=reasons[:8],
        evidence=evidence[:12] if evidence else ["(no notable evidence signals provided)"],
        recommended_actions=recommended_actions,
        rollback=rollback,
        verification_probes=probes,
    )


def render_plan(sig: dict[str, Any], sc: Score) -> str:
    incident_id = str(sig.get("incident_id", "")).strip() or "INC-AEGIS-UNSET"
    detected = str(sig.get("detected_utc", "")).strip() or _utc_now_iso()

    lines: list[str] = []
    lines.append("AEGIS_PLAN v1")
    lines.append(f"Incident: {incident_id}")
    lines.append(f"Detected: {detected}")
    lines.append(f"Severity: {sc.severity}")
    lines.append("Reasons:")
    lines.extend([f"- {r}" for r in (sc.reasons or ["(none)"])])
    lines.append("Evidence:")
    lines.extend([f"- {e}" for e in sc.evidence])
    lines.append("Recommended Actions (proposal only):")
    lines.extend([f"- {a}" for a in sc.recommended_actions])
    lines.append("Rollback Notes:")
    lines.extend([f"- {r}" for r in (sc.rollback or ["(none)"])])
    lines.append("Verification Probes:")
    lines.extend([f"- {p}" for p in sc.verification_probes])
    return "\n".join(lines)


def _load_json(path: str | None) -> object:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def main() -> int:
    ap = argparse.ArgumentParser(description="Score AEGIS signals and print a HITL defense/recovery plan.")
    ap.add_argument("--input", help="Path to JSON input. If omitted, reads from stdin.")
    args = ap.parse_args()

    try:
        obj = _load_json(args.input)
    except Exception as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(obj, dict):
        print("ERROR: input must be a JSON object", file=sys.stderr)
        return 2

    sc = score_signals(obj)
    print(render_plan(obj, sc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

