#!/usr/bin/env python3
"""Summarize ORION policy-gate history and compute rollout/promotion recommendations."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


STAGE1 = ["R3_CRISIS_SAFETY_FIRST", "R4_DESTRUCTIVE_CONFIRMATION", "R6_ANNOUNCE_SKIP"]
STAGE2 = ["R1_CRON_DELEGATE_ATLAS", "R2_COMPLETION_PROOF", "R5_MIXED_INTENT_GATE"]


def _parse_ts(value: str, fallback: dt.datetime) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except Exception:
        return fallback


def _iter_reports(history_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(history_dir.glob("policy-gate-*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("kind") != "orion_policy_gate":
            continue
        obj["_path"] = str(path)
        obj["_mtime"] = path.stat().st_mtime
        reports.append(obj)
    return reports


def _daily_metrics(reports: list[dict[str, Any]], *, min_day: dt.date) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in reports:
        ts = _parse_ts(str(r.get("timestamp") or ""), dt.datetime.fromtimestamp(float(r.get("_mtime", 0)), dt.timezone.utc))
        d = ts.date()
        if d < min_day:
            continue
        key = d.isoformat()
        if key not in out:
            out[key] = {"runs": 0, "violations": 0, "blocking": 0}
        out[key]["runs"] += 1
        s = r.get("summary") or {}
        out[key]["violations"] += int(s.get("violations") or 0)
        out[key]["blocking"] += int(s.get("blocking_violations") or 0)
    return out


def _rule_breakdown(reports: list[dict[str, Any]], *, min_day: dt.date) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"violations": 0, "blocking": 0})
    for r in reports:
        ts = _parse_ts(str(r.get("timestamp") or ""), dt.datetime.fromtimestamp(float(r.get("_mtime", 0)), dt.timezone.utc))
        if ts.date() < min_day:
            continue
        for v in (r.get("violations") or []):
            rid = str((v or {}).get("rule_id") or "")
            if not rid:
                continue
            out[rid]["violations"] += 1
            if bool((v or {}).get("blocking")):
                out[rid]["blocking"] += 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def _promotion_decision(
    *,
    rule_breakdown: dict[str, dict[str, int]],
    daily: dict[str, dict[str, int]],
    min_clean_days: int,
    max_false_positives: int,
) -> dict[str, Any]:
    clean_days = sum(1 for d in daily.values() if d["violations"] == 0)
    total_violations = sum(v["violations"] for v in rule_breakdown.values())

    def stage_status(rules: list[str]) -> dict[str, Any]:
        stage_violations = sum(rule_breakdown.get(r, {}).get("violations", 0) for r in rules)
        eligible = clean_days >= min_clean_days and stage_violations <= max_false_positives
        return {
            "rules": rules,
            "stage_violations": stage_violations,
            "eligible_for_block": eligible,
            "reason": (
                "Eligible: clean-window and threshold satisfied."
                if eligible
                else "Not eligible: waiting for clean-window or lower violation count."
            ),
        }

    return {
        "window_clean_days": clean_days,
        "window_total_violations": total_violations,
        "required_clean_days": min_clean_days,
        "max_false_positives": max_false_positives,
        "stage1": stage_status(STAGE1),
        "stage2": stage_status(STAGE2),
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ORION Policy Gate Scorecard")
    lines.append("")
    lines.append(f"- Window days: `{result['window_days']}`")
    lines.append(f"- Reports scanned: `{result['reports_scanned']}`")
    lines.append(f"- Total violations: `{result['totals']['violations']}`")
    lines.append(f"- Blocking violations: `{result['totals']['blocking_violations']}`")
    lines.append("")

    lines.append("## Daily")
    lines.append("")
    lines.append("| Day | Runs | Violations | Blocking |")
    lines.append("| --- | ---: | ---: | ---: |")
    for day, row in sorted(result["daily"].items()):
        lines.append(f"| {day} | {row['runs']} | {row['violations']} | {row['blocking']} |")
    if not result["daily"]:
        lines.append("| (none) | 0 | 0 | 0 |")
    lines.append("")

    lines.append("## Rule Breakdown")
    lines.append("")
    lines.append("| Rule | Violations | Blocking |")
    lines.append("| --- | ---: | ---: |")
    for rid, row in result["rule_breakdown"].items():
        lines.append(f"| {rid} | {row['violations']} | {row['blocking']} |")
    if not result["rule_breakdown"]:
        lines.append("| (none) | 0 | 0 |")
    lines.append("")

    promo = result["promotion"]
    lines.append("## Promotion Gate")
    lines.append("")
    lines.append(f"- Clean days in window: `{promo['window_clean_days']}` / `{promo['required_clean_days']}`")
    lines.append(f"- Violation threshold: `<= {promo['max_false_positives']}`")
    lines.append("")

    for stage_name in ("stage1", "stage2"):
        stage = promo[stage_name]
        lines.append(f"### {stage_name.upper()}")
        lines.append("")
        lines.append(f"- Rules: `{', '.join(stage['rules'])}`")
        lines.append(f"- Stage violations: `{stage['stage_violations']}`")
        lines.append(f"- Eligible for block: `{stage['eligible_for_block']}`")
        lines.append(f"- Reason: {stage['reason']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build ORION policy gate scorecard + promotion recommendations.")
    ap.add_argument("--history-dir", default="eval/history")
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument("--min-clean-days", type=int, default=7)
    ap.add_argument("--max-false-positives", type=int, default=0)
    ap.add_argument("--output-json", default="eval/policy_gate_latest.json")
    ap.add_argument("--output-md", default="eval/policy_gate_latest.md")
    args = ap.parse_args()

    history_dir = Path(args.history_dir).resolve()
    reports = _iter_reports(history_dir)

    now = dt.datetime.now(dt.timezone.utc).date()
    min_day = now - dt.timedelta(days=max(1, int(args.window_days)) - 1)

    daily = _daily_metrics(reports, min_day=min_day)
    rule_breakdown = _rule_breakdown(reports, min_day=min_day)

    total_violations = sum(int((r.get("summary") or {}).get("violations") or 0) for r in reports)
    total_blocking = sum(int((r.get("summary") or {}).get("blocking_violations") or 0) for r in reports)

    result = {
        "kind": "orion_policy_scorecard",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "history_dir": str(history_dir),
        "window_days": max(1, int(args.window_days)),
        "reports_scanned": len(reports),
        "totals": {
            "violations": total_violations,
            "blocking_violations": total_blocking,
        },
        "daily": daily,
        "rule_breakdown": rule_breakdown,
    }
    result["promotion"] = _promotion_decision(
        rule_breakdown=rule_breakdown,
        daily=daily,
        min_clean_days=max(1, int(args.min_clean_days)),
        max_false_positives=max(0, int(args.max_false_positives)),
    )

    output_json = Path(args.output_json).resolve()
    output_md = Path(args.output_md).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_render_markdown(result), encoding="utf-8")

    print("POLICY_SCORECARD")
    print(f"reports_scanned: {len(reports)}")
    print(f"output_json: {output_json}")
    print(f"output_md: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
