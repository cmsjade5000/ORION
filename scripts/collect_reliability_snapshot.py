#!/usr/bin/env python3
"""
Collect a 24h reliability snapshot for ORION runtime and write eval artifacts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
from collections import Counter
from pathlib import Path


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def _parse_lane_waits(log_path: Path, hours: int) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=hours)
    line_re = re.compile(r"^(\d{4}-\d{2}-\d{2}T[^ ]+)")
    wait_re = re.compile(r"lane wait exceeded: lane=([^ ]+) waitedMs=(\d+) queueAhead=(\d+)")
    waits: list[dict] = []
    if log_path.exists():
        for line in log_path.read_text(errors="ignore").splitlines():
            m = line_re.match(line)
            if not m:
                continue
            try:
                ts = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff:
                continue
            wm = wait_re.search(line)
            if not wm:
                continue
            waits.append(
                {
                    "ts": ts.isoformat(),
                    "lane": wm.group(1),
                    "waited_ms": int(wm.group(2)),
                    "queue_ahead": int(wm.group(3)),
                }
            )
    values = [w["waited_ms"] for w in waits]
    return {
        "hours": hours,
        "count": len(waits),
        "max_ms": max(values) if values else 0,
        "avg_ms": round(statistics.mean(values), 1) if values else 0.0,
        "p95_ms": _p95(values),
        "by_lane": dict(Counter(w["lane"] for w in waits)),
    }


def _cron_stats(jobs_path: Path) -> dict:
    if not jobs_path.exists():
        return {"total": 0, "enabled": 0, "disabled": 0, "by_agent": {}, "by_channel": {}}
    data = json.loads(jobs_path.read_text())
    jobs = data.get("jobs", [])
    enabled = [j for j in jobs if j.get("enabled")]
    return {
        "total": len(jobs),
        "enabled": len(enabled),
        "disabled": len(jobs) - len(enabled),
        "by_agent": dict(Counter(j.get("agentId", "unknown") for j in enabled)),
        "by_channel": dict(Counter((j.get("delivery") or {}).get("channel", "none") for j in enabled)),
    }


def _delivery_queue(queue_dir: Path) -> dict:
    if not queue_dir.exists():
        return {"files": 0, "by_channel": {}, "top_errors": []}
    files = list(queue_dir.glob("*.json"))
    by_channel: Counter[str] = Counter()
    errs: Counter[str] = Counter()
    for path in files:
        try:
            item = json.loads(path.read_text())
        except Exception:
            continue
        by_channel[item.get("channel", "unknown")] += 1
        err = (item.get("lastError") or "").strip()
        if err:
            errs[err] += 1
    return {
        "files": len(files),
        "by_channel": dict(by_channel),
        "top_errors": [{"error": k, "count": v} for k, v in errs.most_common(5)],
    }


def _eval_gate(compare_path: Path) -> dict:
    if not compare_path.exists():
        return {"status": "missing"}
    data = json.loads(compare_path.read_text())
    gate = data.get("gate", {})
    return {
        "status": "pass" if gate.get("passed") else "fail",
        "reasons": gate.get("reasons", []),
        "metrics": data.get("metrics", {}),
    }


def _render_md(report: dict) -> str:
    lane = report["lane_wait_24h"]
    cron = report["cron"]
    queue = report["delivery_queue"]
    gate = report["eval_gate"]
    lines = [
        "# Reliability Snapshot",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Window: last `{lane['hours']}h`",
        "",
        "## Lane Wait",
        "",
        f"- Count: `{lane['count']}`",
        f"- Max: `{lane['max_ms']} ms`",
        f"- P95: `{lane['p95_ms']} ms`",
        f"- By lane: `{lane['by_lane']}`",
        "",
        "## Cron",
        "",
        f"- Total / Enabled / Disabled: `{cron['total']} / {cron['enabled']} / {cron['disabled']}`",
        f"- By agent: `{cron['by_agent']}`",
        f"- By delivery channel: `{cron['by_channel']}`",
        "",
        "## Delivery Queue",
        "",
        f"- Files: `{queue['files']}`",
        f"- By channel: `{queue['by_channel']}`",
        f"- Top errors: `{queue['top_errors']}`",
        "",
        "## Eval Gate",
        "",
        f"- Status: `{gate['status']}`",
        f"- Reasons: `{gate['reasons']}`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect ORION reliability snapshot artifacts.")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--log-path", default="~/.openclaw/logs/gateway.err.log")
    ap.add_argument("--jobs-path", default="~/.openclaw/cron/jobs.json")
    ap.add_argument("--queue-dir", default="~/.openclaw/delivery-queue")
    ap.add_argument("--eval-compare", default="eval/latest_compare.json")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default="eval/reliability-latest.md")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    output_json = Path(args.output_json) if args.output_json else Path(f"eval/history/reliability-{ts}.json")
    output_md = Path(args.output_md)

    report = {
        "kind": "reliability_snapshot",
        "generated_at": now.isoformat(),
        "lane_wait_24h": _parse_lane_waits(Path(args.log_path).expanduser(), args.hours),
        "cron": _cron_stats(Path(args.jobs_path).expanduser()),
        "delivery_queue": _delivery_queue(Path(args.queue_dir).expanduser()),
        "eval_gate": _eval_gate(Path(args.eval_compare)),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(_render_md(report), encoding="utf-8")

    print("RELIABILITY_SNAPSHOT")
    print(f"json: {output_json.resolve()}")
    print(f"md: {output_md.resolve()}")
    print(f"lane_wait_count: {report['lane_wait_24h']['count']}")
    print(f"lane_wait_p95_ms: {report['lane_wait_24h']['p95_ms']}")
    print(f"cron_enabled: {report['cron']['enabled']}")
    print(f"delivery_queue_files: {report['delivery_queue']['files']}")
    print(f"eval_gate: {report['eval_gate']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
