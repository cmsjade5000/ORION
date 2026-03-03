#!/usr/bin/env python3
"""
Record an automated canary health check entry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo


SECTION = "## Automated Canary Checks"
TABLE_HEAD = "| Timestamp (ET) | Candidate | Eval Gate | Lane Wait Count | Lane Wait P95 (ms) | Delivery Queue | Decision | Evidence |"
TABLE_SEP = "| --- | --- | --- | ---: | ---: | ---: | --- | --- |"


def _latest_reliability(history_dir: Path) -> Path:
    files = sorted(history_dir.glob("reliability-*.json"))
    if not files:
        raise FileNotFoundError(f"No reliability snapshot found in {history_dir}")
    return files[-1]


def _load_eval_gate(compare_path: Path) -> tuple[str, list[str]]:
    if not compare_path.exists():
        return "missing", ["missing eval/latest_compare.json"]
    data = json.loads(compare_path.read_text(encoding="utf-8"))
    gate = data.get("gate", {})
    return ("pass" if gate.get("passed") else "fail"), list(gate.get("reasons") or [])


def _load_reliability(snapshot_path: Path) -> dict:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    lane = data.get("lane_wait_24h", {})
    queue = data.get("delivery_queue", {})
    return {
        "count": int(lane.get("count", 0)),
        "p95_ms": int(lane.get("p95_ms", 0)),
        "queue_files": int(queue.get("files", 0)),
    }


def _evaluate_slo(
    eval_gate: str,
    eval_reasons: list[str],
    rel: dict,
    max_lane_wait_count: int,
    max_lane_wait_p95_ms: int,
    max_delivery_queue_files: int,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if eval_gate != "pass":
        if eval_reasons:
            for reason in eval_reasons:
                failures.append(f"eval_gate:{reason}")
        else:
            failures.append("eval_gate:not_pass")
    if rel["count"] > max_lane_wait_count:
        failures.append(
            f"lane_wait_count_exceeded:{rel['count']}>{max_lane_wait_count}"
        )
    if rel["p95_ms"] > max_lane_wait_p95_ms:
        failures.append(
            f"lane_wait_p95_exceeded:{rel['p95_ms']}>{max_lane_wait_p95_ms}"
        )
    if rel["queue_files"] > max_delivery_queue_files:
        failures.append(
            f"delivery_queue_exceeded:{rel['queue_files']}>{max_delivery_queue_files}"
        )
    return len(failures) == 0, failures


def _default_streak_state(timezone: str) -> dict:
    return {
        "kind": "canary_streak_state",
        "version": 1,
        "timezone": timezone,
        "candidates": {},
    }


def _load_streak_state(state_path: Path, timezone: str) -> dict:
    if not state_path.exists():
        return _default_streak_state(timezone)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid streak state payload: {state_path}")
    if not isinstance(data.get("candidates"), dict):
        data["candidates"] = {}
    if "kind" not in data:
        data["kind"] = "canary_streak_state"
    if "version" not in data:
        data["version"] = 1
    if "timezone" not in data:
        data["timezone"] = timezone
    return data


def _write_streak_state(state_path: Path, state: dict, now_et: dt.datetime, timezone: str) -> None:
    state["kind"] = "canary_streak_state"
    state["version"] = 1
    state["timezone"] = timezone
    state["updated_at_et"] = now_et.strftime("%Y-%m-%d %H:%M")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _to_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _to_nonnegative_int(value: object) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return 0
    return out if out >= 0 else 0


def _update_candidate_streak(
    state: dict,
    candidate: str,
    run_date: dt.date,
    run_stamp: str,
    slo_pass: bool,
) -> tuple[int, dict]:
    candidates = state.setdefault("candidates", {})
    prior = candidates.get(candidate, {})
    if not isinstance(prior, dict):
        prior = {}

    prior_streak = _to_nonnegative_int(prior.get("streak_days"))
    last_pass_date = _to_date(prior.get("last_pass_date_et"))

    if slo_pass:
        if last_pass_date == run_date:
            streak_days = prior_streak if prior_streak > 0 else 1
        elif last_pass_date and (run_date - last_pass_date).days == 1:
            streak_days = prior_streak + 1 if prior_streak > 0 else 1
        else:
            streak_days = 1
        last_pass_date_et = run_date.isoformat()
        last_result = "pass"
    else:
        streak_days = 0
        last_pass_date_et = None
        last_result = "fail"

    updated = dict(prior)
    updated["streak_days"] = streak_days
    updated["last_run_date_et"] = run_date.isoformat()
    updated["last_result"] = last_result
    updated["updated_at_et"] = run_stamp
    if last_pass_date_et is None:
        updated.pop("last_pass_date_et", None)
    else:
        updated["last_pass_date_et"] = last_pass_date_et

    candidates[candidate] = updated
    return streak_days, updated


def _ensure_section(lines: list[str]) -> int:
    if SECTION in lines:
        return lines.index(SECTION)
    lines.extend(["", SECTION, "", TABLE_HEAD, TABLE_SEP])
    return len(lines) - 4


def _upsert_row(lines: list[str], section_idx: int, row: str, timestamp_key: str) -> list[str]:
    end_idx = len(lines)
    for i in range(section_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end_idx = i
            break

    # Ensure table headers
    if TABLE_HEAD not in lines[section_idx + 1 : end_idx]:
        lines.insert(section_idx + 1, "")
        lines.insert(section_idx + 2, TABLE_HEAD)
        lines.insert(section_idx + 3, TABLE_SEP)
        end_idx += 3

    # Update existing row if timestamp matches
    for i in range(section_idx + 1, end_idx):
        if lines[i].startswith(f"| {timestamp_key} |"):
            lines[i] = row
            return lines

    # Insert after separator
    sep_idx = lines.index(TABLE_SEP, section_idx + 1, end_idx)
    lines.insert(sep_idx + 1, row)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Append automated canary health status.")
    ap.add_argument("--candidate", default="openprose-workflow-2026-03")
    ap.add_argument("--scorecard", default="docs/skills/canary-results-2026-03.md")
    ap.add_argument("--compare", default="eval/latest_compare.json")
    ap.add_argument("--history-dir", default="eval/history")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--timezone", default="America/New_York")
    ap.add_argument("--max-lane-wait-count", type=int, default=6)
    ap.add_argument("--max-lane-wait-p95-ms", type=int, default=10000)
    ap.add_argument("--max-delivery-queue-files", type=int, default=0)
    ap.add_argument("--streak-target", type=int, default=7)
    ap.add_argument("--streak-state", default=None)
    args = ap.parse_args()

    scorecard = Path(args.scorecard)
    compare = Path(args.compare)
    history_dir = Path(args.history_dir)
    streak_state = Path(args.streak_state) if args.streak_state else history_dir / "canary-streak-state-v1.json"
    streak_target = args.streak_target if args.streak_target > 0 else 7

    now_et = dt.datetime.now(ZoneInfo(args.timezone))
    stamp = now_et.strftime("%Y-%m-%d %H:%M")
    run_date = now_et.date()
    eval_gate, reasons = _load_eval_gate(compare)
    snapshot = _latest_reliability(history_dir)
    rel = _load_reliability(snapshot)
    slo_pass, slo_failures = _evaluate_slo(
        eval_gate=eval_gate,
        eval_reasons=reasons,
        rel=rel,
        max_lane_wait_count=args.max_lane_wait_count,
        max_lane_wait_p95_ms=args.max_lane_wait_p95_ms,
        max_delivery_queue_files=args.max_delivery_queue_files,
    )
    state = _load_streak_state(streak_state, args.timezone)
    streak_days, streak_record = _update_candidate_streak(
        state=state,
        candidate=args.candidate,
        run_date=run_date,
        run_stamp=stamp,
        slo_pass=slo_pass,
    )
    _write_streak_state(streak_state, state, now_et, args.timezone)

    promotion_eligible = slo_pass and streak_days >= streak_target
    if promotion_eligible:
        decision = "promote"
    elif slo_pass:
        decision = "continue"
    else:
        decision = "hold"
    decision_cell = f"{decision} ({streak_days}/{streak_target})"

    evidence = f"`{snapshot.as_posix()}`"
    row = (
        f"| {stamp} | {args.candidate} | {eval_gate} | "
        f"{rel['count']} | {rel['p95_ms']} | {rel['queue_files']} | {decision_cell} | {evidence} |"
    )

    lines = scorecard.read_text(encoding="utf-8").splitlines() if scorecard.exists() else []
    sec_idx = _ensure_section(lines)
    lines = _upsert_row(lines, sec_idx, row, stamp)
    scorecard.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = {
        "kind": "canary_health_check",
        "timestamp_et": stamp,
        "candidate": args.candidate,
        "eval_gate": eval_gate,
        "eval_gate_reasons": reasons,
        "lane_wait_count": rel["count"],
        "lane_wait_p95_ms": rel["p95_ms"],
        "delivery_queue_files": rel["queue_files"],
        "slo_pass": slo_pass,
        "slo_failures": slo_failures,
        "streak_days": streak_days,
        "streak_target": streak_target,
        "promotion_eligible": promotion_eligible,
        "decision": decision,
        "decision_display": decision_cell,
        "streak_state": streak_state.as_posix(),
        "candidate_streak_record": streak_record,
        "evidence": snapshot.as_posix(),
        "scorecard": scorecard.as_posix(),
        "thresholds": {
            "max_lane_wait_count": args.max_lane_wait_count,
            "max_lane_wait_p95_ms": args.max_lane_wait_p95_ms,
            "max_delivery_queue_files": args.max_delivery_queue_files,
        },
    }
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANARY_HEALTH_CHECK")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
