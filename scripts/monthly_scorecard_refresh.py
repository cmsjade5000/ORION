#!/usr/bin/env python3
"""
Refresh the monthly scorecard from eval artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "America/New_York"
SLO_R1_MAX_LANE_WAIT_COUNT = 6
SLO_R2_MAX_LANE_WAIT_P95_MS = 10000
SLO_R4_MAX_DELIVERY_QUEUE = 0


@dataclass(frozen=True)
class ReliabilitySnapshot:
    path: Path
    timestamp_utc: dt.datetime
    date_et: str
    lane_count: int | None
    lane_p95_ms: int | None
    cron_enabled: int | None
    cron_total: int | None
    queue_files: int | None
    eval_gate: str


@dataclass(frozen=True)
class CanaryStatus:
    source: str
    source_path: str
    candidate: str
    decision: str
    timestamp_et: str
    streak_days: int | None
    streak_target: int | None
    evidence: str


def _abs_path(path: Path) -> str:
    return path.expanduser().resolve(strict=False).as_posix()


def _parse_iso_datetime(value: str | None) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _parse_reliability_name_timestamp(path: Path) -> dt.datetime | None:
    match = re.match(r"^reliability-(\d{8})-(\d{6})\.json$", path.name)
    if not match:
        return None
    stamp = f"{match.group(1)}{match.group(2)}"
    try:
        parsed = dt.datetime.strptime(stamp, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc)


def _parse_canary_name_timestamp(path: Path) -> dt.datetime | None:
    match = re.search(r"(\d{8}-\d{6})\.json$", path.name)
    if not match:
        return None
    try:
        parsed = dt.datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt.timezone.utc)


def _safe_load_json(path: Path, warnings: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        warnings.append(f"missing json: {_abs_path(path)}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"failed json load: {_abs_path(path)} ({exc})")
        return None
    if not isinstance(data, dict):
        warnings.append(f"invalid json object: {_abs_path(path)}")
        return None
    return data


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_value(value: Any) -> str:
    if value is None:
        return "unknown"
    return str(value)


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value * 100:.1f}%"


def _fmt_delta(current: float | int | None, baseline: float | int | None, *, suffix: str = "") -> str:
    if current is None or baseline is None:
        return "unknown"
    delta = current - baseline
    if isinstance(delta, float):
        return f"{delta:+.1f}{suffix}"
    return f"{int(delta):+d}{suffix}"


def _fmt_delta_pp(current: float | None, baseline: float | None) -> str:
    if current is None or baseline is None:
        return "unknown"
    return f"{(current - baseline) * 100:+.1f} pp"


def _status_label(value: bool | None) -> str:
    if value is None:
        return "UNKNOWN"
    return "PASS" if value else "FAIL"


def _month_label(month: str) -> str:
    try:
        parsed = dt.datetime.strptime(month, "%Y-%m")
    except ValueError:
        return month
    return parsed.strftime("%B %Y")


def _load_reliability_snapshots(history_dir: Path, timezone: str, warnings: list[str]) -> list[ReliabilitySnapshot]:
    tz = ZoneInfo(timezone)
    snapshots: list[ReliabilitySnapshot] = []
    for path in sorted(history_dir.glob("reliability-*.json")):
        payload = _safe_load_json(path, warnings)
        if payload is None:
            continue
        generated_at = _parse_iso_datetime(payload.get("generated_at"))
        timestamp_utc = generated_at or _parse_reliability_name_timestamp(path)
        if timestamp_utc is None:
            warnings.append(f"missing reliability timestamp: {_abs_path(path)}")
            continue
        lane = payload.get("lane_wait_24h", {})
        cron = payload.get("cron", {})
        queue = payload.get("delivery_queue", {})
        gate = payload.get("eval_gate", {})
        snapshots.append(
            ReliabilitySnapshot(
                path=path,
                timestamp_utc=timestamp_utc,
                date_et=timestamp_utc.astimezone(tz).date().isoformat(),
                lane_count=_to_int(lane.get("count")),
                lane_p95_ms=_to_int(lane.get("p95_ms")),
                cron_enabled=_to_int(cron.get("enabled")),
                cron_total=_to_int(cron.get("total")),
                queue_files=_to_int(queue.get("files")),
                eval_gate=str(gate.get("status", "unknown")),
            )
        )
    snapshots.sort(key=lambda item: (item.timestamp_utc, item.path.as_posix()))
    return snapshots


def _extract_baseline(baseline_data: dict[str, Any] | None) -> dict[str, Any]:
    runtime = baseline_data.get("runtime_baseline", {}) if baseline_data else {}
    summary = baseline_data.get("summary", {}) if baseline_data else {}
    passed = _to_int(summary.get("pass"))
    failed = _to_int(summary.get("fail"))
    total = None
    pass_rate = None
    if passed is not None and failed is not None:
        total = passed + failed
        if total > 0:
            pass_rate = passed / total
    return {
        "captured_at": _fmt_value(baseline_data.get("captured_at") if baseline_data else None),
        "lane_count": _to_int(runtime.get("lane_wait_24h_count")) if isinstance(runtime, dict) else None,
        "lane_p95_ms": _to_int(runtime.get("lane_wait_24h_p95_ms")) if isinstance(runtime, dict) else None,
        "cron_enabled": _to_int(runtime.get("cron_enabled")) if isinstance(runtime, dict) else None,
        "cron_total": _to_int(runtime.get("cron_total")) if isinstance(runtime, dict) else None,
        "queue_files": _to_int(runtime.get("delivery_queue_files")) if isinstance(runtime, dict) else None,
        "confidence": _to_int(baseline_data.get("confidence") if baseline_data else None),
        "eval_pass_rate": pass_rate,
        "eval_passed": passed,
        "eval_total": total,
        "eval_safety_zeros": _to_int(summary.get("safety_zeros")) if isinstance(summary, dict) else None,
        "cron_channel_mismatches": _to_int(runtime.get("cron_channel_mismatches")) if isinstance(runtime, dict) else None,
    }


def _count_current_cron_channel_mismatches(warnings: list[str]) -> int | None:
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    jobs_path = Path.home() / ".openclaw" / "cron" / "jobs.json"

    if not cfg_path.exists() or not jobs_path.exists():
        warnings.append("missing runtime files for cron channel mismatch check")
        return None

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        jobs_doc = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"failed runtime mismatch check load ({exc})")
        return None

    channels_cfg = cfg.get("channels", {})
    plugins_cfg = (cfg.get("plugins", {}) or {}).get("entries", {})
    jobs = jobs_doc.get("jobs", [])
    if not isinstance(channels_cfg, dict) or not isinstance(plugins_cfg, dict) or not isinstance(jobs, list):
        warnings.append("invalid runtime structure for cron channel mismatch check")
        return None

    enabled_channels = {
        name
        for name, value in channels_cfg.items()
        if isinstance(value, dict) and value.get("enabled") is True
    }
    enabled_plugins = {
        name
        for name, value in plugins_cfg.items()
        if isinstance(value, dict) and value.get("enabled") is True
    }

    mismatches = 0
    for job in jobs:
        if not isinstance(job, dict) or not job.get("enabled"):
            continue
        delivery = job.get("delivery")
        channel = ""
        if isinstance(delivery, dict):
            channel = str(delivery.get("channel", "")).strip().lower()
        if channel in {"", "none", "last"}:
            continue
        if channel not in enabled_channels or channel not in enabled_plugins:
            mismatches += 1

    return mismatches


def _extract_compare(compare_data: dict[str, Any] | None) -> dict[str, Any]:
    metrics = compare_data.get("metrics", {}) if compare_data else {}
    baseline = metrics.get("baseline", {}) if isinstance(metrics, dict) else {}
    current = metrics.get("current", {}) if isinstance(metrics, dict) else {}
    delta = metrics.get("delta", {}) if isinstance(metrics, dict) else {}
    gate = compare_data.get("gate", {}) if compare_data else {}
    thresholds = gate.get("thresholds", {}) if isinstance(gate, dict) else {}
    return {
        "gate_passed": gate.get("passed") if isinstance(gate.get("passed"), bool) else None,
        "gate_reasons": gate.get("reasons") if isinstance(gate.get("reasons"), list) else [],
        "min_confidence": _to_int(thresholds.get("min_confidence")) if isinstance(thresholds, dict) else None,
        "min_pass_rate": _to_float(thresholds.get("min_pass_rate")) if isinstance(thresholds, dict) else None,
        "max_safety_zeros": _to_int(thresholds.get("max_safety_zeros")) if isinstance(thresholds, dict) else None,
        "max_confidence_drop": _to_int(thresholds.get("max_confidence_drop")) if isinstance(thresholds, dict) else None,
        "current_confidence": _to_int(current.get("confidence")) if isinstance(current, dict) else None,
        "current_pass_rate": _to_float(current.get("pass_rate")) if isinstance(current, dict) else None,
        "current_safety_zeros": _to_int(current.get("safety_zeros")) if isinstance(current, dict) else None,
        "baseline_confidence": _to_int(baseline.get("confidence")) if isinstance(baseline, dict) else None,
        "baseline_pass_rate": _to_float(baseline.get("pass_rate")) if isinstance(baseline, dict) else None,
        "baseline_safety_zeros": _to_int(baseline.get("safety_zeros")) if isinstance(baseline, dict) else None,
        "delta_confidence": _to_int(delta.get("confidence")) if isinstance(delta, dict) else None,
        "delta_pass_rate": _to_float(delta.get("pass_rate")) if isinstance(delta, dict) else None,
        "delta_safety_zeros": _to_int(delta.get("safety_zeros")) if isinstance(delta, dict) else None,
    }


def _load_canary_status_from_json(history_dir: Path, timezone: str, warnings: list[str]) -> CanaryStatus | None:
    tz = ZoneInfo(timezone)
    candidates: list[tuple[dt.datetime, Path, dict[str, Any]]] = []
    for path in sorted(history_dir.glob("canary-check*.json")):
        payload = _safe_load_json(path, warnings)
        if payload is None:
            continue
        stamp = _parse_canary_name_timestamp(path)
        stamp_et_raw = payload.get("timestamp_et")
        if stamp is None and isinstance(stamp_et_raw, str):
            try:
                stamp_local = dt.datetime.strptime(stamp_et_raw, "%Y-%m-%d %H:%M")
                stamp = stamp_local.replace(tzinfo=tz).astimezone(dt.timezone.utc)
            except ValueError:
                stamp = None
        if stamp is None:
            continue
        candidates.append((stamp, path, payload))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].as_posix()))
    _, latest_path, latest = candidates[-1]

    decision = str(latest.get("decision_display") or latest.get("decision") or "unknown")
    streak_days = _to_int(latest.get("streak_days"))
    streak_target = _to_int(latest.get("streak_target"))
    evidence = str(latest.get("evidence") or "unknown")
    return CanaryStatus(
        source="canary-check json",
        source_path=_abs_path(latest_path),
        candidate=str(latest.get("candidate") or "unknown"),
        decision=decision,
        timestamp_et=str(latest.get("timestamp_et") or "unknown"),
        streak_days=streak_days,
        streak_target=streak_target,
        evidence=evidence,
    )


def _load_canary_status_from_markdown(path: Path, warnings: list[str]) -> CanaryStatus | None:
    if not path.exists():
        warnings.append(f"missing canary markdown: {_abs_path(path)}")
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"failed canary markdown read: {_abs_path(path)} ({exc})")
        return None

    table_header = "| Timestamp (ET) | Candidate | Eval Gate | Lane Wait Count | Lane Wait P95 (ms) | Delivery Queue | Decision | Evidence |"
    if table_header not in lines:
        return None
    idx = lines.index(table_header)
    for line in lines[idx + 2 :]:
        if not line.startswith("|"):
            if line.strip():
                break
            continue
        parts = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(parts) < 8:
            continue
        decision = parts[6] or "unknown"
        streak_days = None
        streak_target = None
        match = re.search(r"\((\d+)\s*/\s*(\d+)\)", decision)
        if match:
            streak_days = int(match.group(1))
            streak_target = int(match.group(2))
        return CanaryStatus(
            source="canary results markdown",
            source_path=_abs_path(path),
            candidate=parts[1] or "unknown",
            decision=decision,
            timestamp_et=parts[0] or "unknown",
            streak_days=streak_days,
            streak_target=streak_target,
            evidence=parts[7] or "unknown",
        )
    return None


def _build_daily_rows(snapshots: list[ReliabilitySnapshot]) -> list[ReliabilitySnapshot]:
    latest_by_date: dict[str, ReliabilitySnapshot] = {}
    for snap in snapshots:
        prior = latest_by_date.get(snap.date_et)
        if prior is None or snap.timestamp_utc > prior.timestamp_utc:
            latest_by_date[snap.date_et] = snap
    return [latest_by_date[key] for key in sorted(latest_by_date.keys())]


def _render_scorecard(
    *,
    month: str,
    baseline_path: Path,
    compare_path: Path,
    history_dir: Path,
    canary_md_path: Path,
    baseline: dict[str, Any],
    compare: dict[str, Any],
    latest_snapshot: ReliabilitySnapshot | None,
    cron_channel_mismatch_after: int | None,
    daily_rows: list[ReliabilitySnapshot],
    canary: CanaryStatus | None,
    warnings: list[str],
) -> str:
    lane_after = latest_snapshot.lane_count if latest_snapshot else None
    lane_p95_after = latest_snapshot.lane_p95_ms if latest_snapshot else None
    queue_after = latest_snapshot.queue_files if latest_snapshot else None
    cron_enabled_after = latest_snapshot.cron_enabled if latest_snapshot else None
    cron_total_after = latest_snapshot.cron_total if latest_snapshot else None
    eval_gate_after = latest_snapshot.eval_gate if latest_snapshot else "unknown"

    lane_baseline = baseline.get("lane_count")
    lane_p95_baseline = baseline.get("lane_p95_ms")
    queue_baseline = baseline.get("queue_files")
    cron_enabled_baseline = baseline.get("cron_enabled")
    cron_total_baseline = baseline.get("cron_total")
    cron_mismatch_baseline = baseline.get("cron_channel_mismatches")

    r1 = lane_after <= SLO_R1_MAX_LANE_WAIT_COUNT if lane_after is not None else None
    r2 = lane_p95_after <= SLO_R2_MAX_LANE_WAIT_P95_MS if lane_p95_after is not None else None
    r3 = cron_channel_mismatch_after == 0 if cron_channel_mismatch_after is not None else None
    r4 = queue_after <= SLO_R4_MAX_DELIVERY_QUEUE if queue_after is not None else None

    min_confidence = compare.get("min_confidence")
    min_pass_rate = compare.get("min_pass_rate")
    max_safety_zeros = compare.get("max_safety_zeros")
    max_confidence_drop = compare.get("max_confidence_drop")

    c_conf = compare.get("current_confidence")
    c_rate = compare.get("current_pass_rate")
    c_safety = compare.get("current_safety_zeros")
    d_conf = compare.get("delta_confidence")

    e1 = c_conf >= min_confidence if c_conf is not None and min_confidence is not None else None
    e2 = c_rate >= min_pass_rate if c_rate is not None and min_pass_rate is not None else None
    e3 = c_safety <= max_safety_zeros if c_safety is not None and max_safety_zeros is not None else None
    e4 = d_conf >= (-abs(max_confidence_drop)) if d_conf is not None and max_confidence_drop is not None else None

    lines: list[str] = []
    lines.append(f"# Monthly Scorecard - {month} (Generated)")
    lines.append("")
    lines.append("Status: `in progress`")
    lines.append("Owner: ORION main + eval support")
    lines.append(f"Verification window: {_month_label(month)}")
    lines.append("")
    lines.append("## Baseline Snapshot")
    lines.append("")
    lines.append(f"Baseline capture source: `{_abs_path(baseline_path)}`")
    lines.append("")
    lines.append("| Metric | Baseline |")
    lines.append("| --- | --- |")
    lines.append(
        "| Lane wait (count / p95 ms) | "
        f"`{_fmt_value(lane_baseline)} / {_fmt_value(lane_p95_baseline)}` |"
    )
    lines.append(
        "| Cron enabled / total | "
        f"`{_fmt_value(cron_enabled_baseline)} / {_fmt_value(cron_total_baseline)}` |"
    )
    lines.append(f"| Delivery backlog size | `{_fmt_value(queue_baseline)}` |")
    lines.append(f"| Eval confidence | `{_fmt_value(baseline.get('confidence'))}` |")
    lines.append(
        "| Eval pass rate | "
        f"`{_fmt_percent(baseline.get('eval_pass_rate'))}` "
        f"({_fmt_value(baseline.get('eval_passed'))}/{_fmt_value(baseline.get('eval_total'))}) |"
    )
    lines.append(f"| Eval safety zeros | `{_fmt_value(baseline.get('eval_safety_zeros'))}` |")
    lines.append(f"| Captured at | `{_fmt_value(baseline.get('captured_at'))}` |")
    lines.append("")
    lines.append("## After Snapshot")
    lines.append("")
    lines.append(
        "Latest reliability source: "
        f"`{_abs_path(latest_snapshot.path) if latest_snapshot else 'unknown'}`"
    )
    lines.append(f"Latest compare source: `{_abs_path(compare_path)}`")
    lines.append("")
    lines.append("| Metric | After | Delta vs Baseline |")
    lines.append("| --- | --- | --- |")
    lines.append(
        "| Lane wait (count / p95 ms) | "
        f"`{_fmt_value(lane_after)} / {_fmt_value(lane_p95_after)}` | "
        f"`{_fmt_delta(lane_after, lane_baseline)} / {_fmt_delta(lane_p95_after, lane_p95_baseline, suffix=' ms')}` |"
    )
    lines.append(
        "| Cron enabled / total | "
        f"`{_fmt_value(cron_enabled_after)} / {_fmt_value(cron_total_after)}` | "
        f"`{_fmt_delta(cron_enabled_after, cron_enabled_baseline)} enabled` |"
    )
    lines.append(
        f"| Delivery backlog size | `{_fmt_value(queue_after)}` | `{_fmt_delta(queue_after, queue_baseline)}` |"
    )
    lines.append(
        f"| Eval gate status | `{_fmt_value(eval_gate_after)}` | `compare gate: {_status_label(compare.get('gate_passed'))}` |"
    )
    lines.append(
        f"| Eval confidence | `{_fmt_value(compare.get('current_confidence'))}` | `{_fmt_delta(compare.get('current_confidence'), baseline.get('confidence'))}` |"
    )
    lines.append(
        f"| Eval pass rate | `{_fmt_percent(compare.get('current_pass_rate'))}` | `{_fmt_delta_pp(compare.get('current_pass_rate'), baseline.get('eval_pass_rate'))}` |"
    )
    lines.append("")
    lines.append("## Reliability Deltas")
    lines.append("")
    lines.append("| SLO | Target | Baseline | After | Delta | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    lines.append(
        f"| SLO-R1 lane wait count | `<= {SLO_R1_MAX_LANE_WAIT_COUNT}` | "
        f"`{_fmt_value(lane_baseline)}` | `{_fmt_value(lane_after)}` | "
        f"`{_fmt_delta(lane_after, lane_baseline)}` | `{_status_label(r1)}` |"
    )
    lines.append(
        f"| SLO-R2 lane wait p95 (ms) | `<= {SLO_R2_MAX_LANE_WAIT_P95_MS}` | "
        f"`{_fmt_value(lane_p95_baseline)}` | `{_fmt_value(lane_p95_after)}` | "
        f"`{_fmt_delta(lane_p95_after, lane_p95_baseline, suffix=' ms')}` | `{_status_label(r2)}` |"
    )
    lines.append(
        "| SLO-R3 enabled cron to disabled channels/plugins | `0` | "
        f"`{_fmt_value(cron_mismatch_baseline)}` | `{_fmt_value(cron_channel_mismatch_after)}` | "
        f"`{_fmt_delta(cron_channel_mismatch_after, cron_mismatch_baseline)}` | `{_status_label(r3)}` |"
    )
    lines.append(
        f"| SLO-R4 delivery backlog | `<= {SLO_R4_MAX_DELIVERY_QUEUE}` | "
        f"`{_fmt_value(queue_baseline)}` | `{_fmt_value(queue_after)}` | "
        f"`{_fmt_delta(queue_after, queue_baseline)}` | `{_status_label(r4)}` |"
    )
    lines.append("")
    lines.append("## Eval Quality Deltas")
    lines.append("")
    lines.append("| SLO | Target | Baseline | Current | Delta | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    lines.append(
        f"| SLO-E1 confidence | `>= {_fmt_value(min_confidence)}` | "
        f"`{_fmt_value(compare.get('baseline_confidence'))}` | `{_fmt_value(c_conf)}` | "
        f"`{_fmt_delta(c_conf, compare.get('baseline_confidence'))}` | `{_status_label(e1)}` |"
    )
    lines.append(
        f"| SLO-E2 pass rate | `>= {_fmt_percent(min_pass_rate)}` | "
        f"`{_fmt_percent(compare.get('baseline_pass_rate'))}` | `{_fmt_percent(c_rate)}` | "
        f"`{_fmt_delta_pp(c_rate, compare.get('baseline_pass_rate'))}` | `{_status_label(e2)}` |"
    )
    lines.append(
        f"| SLO-E3 safety zeros | `<= {_fmt_value(max_safety_zeros)}` | "
        f"`{_fmt_value(compare.get('baseline_safety_zeros'))}` | `{_fmt_value(c_safety)}` | "
        f"`{_fmt_delta(c_safety, compare.get('baseline_safety_zeros'))}` | `{_status_label(e3)}` |"
    )
    lines.append(
        f"| SLO-E4 confidence drop | `>= -{_fmt_value(max_confidence_drop)}` | "
        "`0` | "
        f"`{_fmt_value(d_conf)}` | `{_fmt_value(d_conf)}` | `{_status_label(e4)}` |"
    )
    lines.append(f"Gate verdict: `{_status_label(compare.get('gate_passed'))}`")
    if compare.get("gate_reasons"):
        lines.append("Gate reasons:")
        for reason in compare["gate_reasons"]:
            lines.append(f"- `{reason}`")
    lines.append("")
    lines.append("## Canary Progress")
    lines.append("")
    lines.append(f"Canary results source: `{_abs_path(canary_md_path)}`")
    if canary is None:
        lines.append("- Latest canary decision: `unknown`")
        lines.append("- Canary streak: `unknown`")
        lines.append("- Evidence: `unknown`")
    else:
        lines.append(f"- Source type: `{canary.source}`")
        lines.append(f"- Source artifact: `{canary.source_path}`")
        lines.append(f"- Candidate: `{canary.candidate}`")
        lines.append(f"- Latest decision: `{canary.decision}`")
        lines.append(f"- Decision timestamp (ET): `{canary.timestamp_et}`")
        if canary.streak_days is None:
            lines.append("- Canary streak: `unknown`")
        elif canary.streak_target is None:
            lines.append(f"- Canary streak: `{canary.streak_days}`")
        else:
            lines.append(f"- Canary streak: `{canary.streak_days}/{canary.streak_target}`")
        lines.append(f"- Evidence: `{canary.evidence}`")
    lines.append("")
    lines.append("## Daily Reliability Log")
    lines.append("")
    lines.append("| Date (ET) | Lane Wait Count | Lane Wait P95 (ms) | Cron Enabled | Delivery Queue | Eval Gate | Snapshot |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- | --- |")
    if daily_rows:
        for snap in daily_rows:
            lines.append(
                f"| {snap.date_et} | {_fmt_value(snap.lane_count)} | {_fmt_value(snap.lane_p95_ms)} | "
                f"{_fmt_value(snap.cron_enabled)} | {_fmt_value(snap.queue_files)} | "
                f"{_fmt_value(snap.eval_gate)} | `{_abs_path(snap.path)}` |"
            )
    else:
        lines.append("| pending | unknown | unknown | unknown | unknown | unknown | `unknown` |")
    lines.append("")
    lines.append("## Artifact References")
    lines.append("")
    lines.append(f"- Baseline JSON: `{_abs_path(baseline_path)}`")
    lines.append(f"- Latest compare JSON: `{_abs_path(compare_path)}`")
    lines.append(f"- Reliability history dir: `{_abs_path(history_dir)}`")
    lines.append(f"- Canary results markdown: `{_abs_path(canary_md_path)}`")
    if latest_snapshot:
        lines.append(f"- Latest reliability snapshot: `{_abs_path(latest_snapshot.path)}`")
    if canary:
        lines.append(f"- Latest canary status artifact: `{canary.source_path}`")
    if warnings:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        lines.append("Artifacts missing/unreadable during generation:")
        for warning in sorted(set(warnings)):
            lines.append(f"- `{warning}`")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh monthly scorecard from eval artifacts.")
    parser.add_argument("--month", default=dt.datetime.now().strftime("%Y-%m"))
    parser.add_argument("--baseline-json", default=None)
    parser.add_argument("--latest-compare-json", default=None)
    parser.add_argument("--history-dir", default=None)
    parser.add_argument("--canary-results-md", default=None)
    parser.add_argument("--output-scorecard", default=None)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    args = parser.parse_args()

    baseline_path = Path(args.baseline_json or f"eval/history/baseline-{args.month}.json")
    compare_path = Path(args.latest_compare_json or "eval/latest_compare.json")
    history_dir = Path(args.history_dir or "eval/history")
    canary_md_path = Path(args.canary_results_md or f"docs/skills/canary-results-{args.month}.md")
    output_path = Path(args.output_scorecard or f"eval/monthly-scorecard-{args.month}.md")

    warnings: list[str] = []

    baseline_data = _safe_load_json(baseline_path, warnings)
    compare_data = _safe_load_json(compare_path, warnings)
    baseline = _extract_baseline(baseline_data)
    compare = _extract_compare(compare_data)

    if history_dir.exists():
        snapshots = _load_reliability_snapshots(history_dir, args.timezone, warnings)
    else:
        snapshots = []
        warnings.append(f"missing history dir: {_abs_path(history_dir)}")
    latest_snapshot = snapshots[-1] if snapshots else None
    daily_rows = _build_daily_rows(snapshots)
    cron_channel_mismatch_after = _count_current_cron_channel_mismatches(warnings)

    canary = _load_canary_status_from_json(history_dir, args.timezone, warnings) if history_dir.exists() else None
    if canary is None:
        canary = _load_canary_status_from_markdown(canary_md_path, warnings)

    markdown = _render_scorecard(
        month=args.month,
        baseline_path=baseline_path,
        compare_path=compare_path,
        history_dir=history_dir,
        canary_md_path=canary_md_path,
        baseline=baseline,
        compare=compare,
        latest_snapshot=latest_snapshot,
        cron_channel_mismatch_after=cron_channel_mismatch_after,
        daily_rows=daily_rows,
        canary=canary,
        warnings=warnings,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print("MONTHLY_SCORECARD_REFRESH")
    print(f"output_scorecard: {_abs_path(output_path)}")
    print(f"month: {args.month}")
    print(f"daily_rows: {len(daily_rows)}")
    if latest_snapshot:
        print(f"latest_reliability: {_abs_path(latest_snapshot.path)}")
    else:
        print("latest_reliability: unknown")
    print(f"canary_status: {canary.decision if canary else 'unknown'}")
    if warnings:
        print(f"warnings: {len(sorted(set(warnings)))}")
    else:
        print("warnings: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
