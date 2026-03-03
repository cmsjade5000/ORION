#!/usr/bin/env python3
"""Detect lane-wait hot windows and correlate nearby cron runs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LANE_WAIT_RE = re.compile(
    r"^(?P<ts>\S+).*lane wait exceeded: lane=(?P<lane>\S+)\s+"
    r"waitedMs=(?P<waited_ms>\d+)\s+queueAhead=(?P<queue_ahead>-?\d+)"
)


@dataclass(frozen=True)
class LaneEvent:
    timestamp_ms: int
    timestamp_iso: str
    lane: str
    waited_ms: int
    queue_ahead: int


@dataclass(frozen=True)
class CronRun:
    run_at_ms: int
    run_at_iso: str
    job_id: str
    job_name: str
    duration_ms: int | None
    source_file: str


def iso_to_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def ms_to_iso(value_ms: int) -> str:
    return datetime.fromtimestamp(value_ms / 1000, tz=timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find lane-wait hot windows and correlate cron runs near those windows."
        )
    )
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours.")
    parser.add_argument(
        "--bucket-minutes",
        type=int,
        default=1,
        help="Bucket size in minutes for hot window ranking.",
    )
    parser.add_argument("--top", type=int, default=10, help="Top hot windows to include.")
    parser.add_argument(
        "--correlation-window-seconds",
        type=int,
        default=90,
        help="Correlate runs within +/- this many seconds from each hot window.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Output JSON path. Defaults to eval/history/lane-hotspots-<ts>.json",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Output Markdown path. Defaults to eval/history/lane-hotspots-<ts>.md",
    )
    return parser.parse_args()


def warn(warnings: list[str], message: str) -> None:
    warnings.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


def load_job_names(jobs_path: Path, warnings: list[str]) -> dict[str, str]:
    if not jobs_path.exists():
        warn(warnings, f"jobs map not found: {jobs_path}")
        return {}

    try:
        payload = json.loads(jobs_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        warn(warnings, f"failed to parse jobs map at {jobs_path}: {exc}")
        return {}

    names: dict[str, str] = {}
    jobs_node: Any
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        jobs_node = payload["jobs"]
    elif isinstance(payload, list):
        jobs_node = payload
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, str):
                names[str(key)] = value
        return names
    else:
        warn(warnings, f"unexpected jobs map shape in {jobs_path}")
        return {}

    for entry in jobs_node:
        if isinstance(entry, dict):
            job_id = entry.get("id")
            job_name = entry.get("name")
            if isinstance(job_id, str) and isinstance(job_name, str):
                names[job_id] = job_name

    return names


def load_lane_events(
    lane_log_path: Path, cutoff_ms: int, now_ms: int, warnings: list[str]
) -> list[LaneEvent]:
    if not lane_log_path.exists():
        warn(warnings, f"lane log not found: {lane_log_path}")
        return []

    events: list[LaneEvent] = []
    with lane_log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            match = LANE_WAIT_RE.search(line)
            if not match:
                continue
            try:
                ts_iso = match.group("ts")
                ts_ms = iso_to_ms(ts_iso)
                if ts_ms < cutoff_ms or ts_ms > now_ms:
                    continue
                events.append(
                    LaneEvent(
                        timestamp_ms=ts_ms,
                        timestamp_iso=ts_iso,
                        lane=match.group("lane"),
                        waited_ms=int(match.group("waited_ms")),
                        queue_ahead=int(match.group("queue_ahead")),
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                warn(
                    warnings,
                    f"failed to parse lane event at {lane_log_path}:{line_no}: {exc}",
                )
    return events


def load_cron_runs(
    runs_dir: Path,
    job_names: dict[str, str],
    cutoff_ms: int,
    corr_window_ms: int,
    warnings: list[str],
) -> list[CronRun]:
    if not runs_dir.exists():
        warn(warnings, f"cron runs dir not found: {runs_dir}")
        return []

    run_files = sorted(runs_dir.glob("*.jsonl"))
    if not run_files:
        warn(warnings, f"no cron run files found in {runs_dir}")
        return []

    runs: list[CronRun] = []
    scan_min_ms = cutoff_ms - corr_window_ms
    for run_file in run_files:
        with run_file.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    warn(warnings, f"invalid json in {run_file}:{line_no}: {exc}")
                    continue

                if not isinstance(payload, dict):
                    continue

                run_at_ms = payload.get("runAtMs")
                if not isinstance(run_at_ms, (int, float)):
                    continue
                run_at_ms = int(run_at_ms)
                if run_at_ms < scan_min_ms:
                    continue

                job_id = payload.get("jobId")
                if not isinstance(job_id, str) or not job_id:
                    job_id = run_file.stem

                duration_node = payload.get("durationMs", payload.get("duration"))
                duration_ms = int(duration_node) if isinstance(duration_node, (int, float)) else None

                runs.append(
                    CronRun(
                        run_at_ms=run_at_ms,
                        run_at_iso=ms_to_iso(run_at_ms),
                        job_id=job_id,
                        job_name=job_names.get(job_id, "unknown"),
                        duration_ms=duration_ms,
                        source_file=str(run_file),
                    )
                )
    runs.sort(key=lambda item: item.run_at_ms)
    return runs


def summarize_windows(
    events: list[LaneEvent],
    runs: list[CronRun],
    bucket_minutes: int,
    top_n: int,
    corr_window_seconds: int,
) -> list[dict[str, Any]]:
    bucket_ms = bucket_minutes * 60 * 1000
    corr_window_ms = corr_window_seconds * 1000

    grouped: dict[int, list[LaneEvent]] = defaultdict(list)
    for event in events:
        bucket_start = (event.timestamp_ms // bucket_ms) * bucket_ms
        grouped[bucket_start].append(event)

    ordered = sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), -max(evt.waited_ms for evt in item[1]), item[0]),
    )
    selected = ordered[:top_n]

    windows: list[dict[str, Any]] = []
    for rank, (bucket_start, bucket_events) in enumerate(selected, start=1):
        bucket_end = bucket_start + bucket_ms
        corr_start = bucket_start - corr_window_ms
        corr_end = bucket_end + corr_window_ms
        window_center = bucket_start + (bucket_ms // 2)

        correlated_runs = [
            run for run in runs if corr_start <= run.run_at_ms <= corr_end
        ]

        lane_counter = Counter(evt.lane for evt in bucket_events)
        lane_stats = []
        for lane_name, lane_count in lane_counter.most_common():
            lane_events = [evt for evt in bucket_events if evt.lane == lane_name]
            lane_stats.append(
                {
                    "lane": lane_name,
                    "count": lane_count,
                    "maxWaitMs": max(evt.waited_ms for evt in lane_events),
                    "avgWaitMs": round(
                        sum(evt.waited_ms for evt in lane_events) / len(lane_events), 2
                    ),
                }
            )

        job_groups: dict[str, list[CronRun]] = defaultdict(list)
        for run in correlated_runs:
            job_groups[run.job_id].append(run)

        correlated_jobs = []
        for job_id, job_runs in sorted(
            job_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            durations = [run.duration_ms for run in job_runs if run.duration_ms is not None]
            correlated_jobs.append(
                {
                    "jobId": job_id,
                    "jobName": job_runs[0].job_name,
                    "runCount": len(job_runs),
                    "maxDurationMs": max(durations) if durations else None,
                    "avgDurationMs": (
                        round(sum(durations) / len(durations), 2) if durations else None
                    ),
                }
            )

        window = {
            "rank": rank,
            "windowStartMs": bucket_start,
            "windowEndMs": bucket_end,
            "windowStart": ms_to_iso(bucket_start),
            "windowEnd": ms_to_iso(bucket_end),
            "eventCount": len(bucket_events),
            "maxWaitMs": max(evt.waited_ms for evt in bucket_events),
            "avgWaitMs": round(
                sum(evt.waited_ms for evt in bucket_events) / len(bucket_events), 2
            ),
            "lanes": lane_stats,
            "events": [
                {
                    "timestamp": evt.timestamp_iso,
                    "timestampMs": evt.timestamp_ms,
                    "lane": evt.lane,
                    "waitedMs": evt.waited_ms,
                    "queueAhead": evt.queue_ahead,
                }
                for evt in sorted(bucket_events, key=lambda item: item.timestamp_ms)
            ],
            "correlation": {
                "windowSeconds": corr_window_seconds,
                "windowStartMs": corr_start,
                "windowEndMs": corr_end,
                "windowStart": ms_to_iso(corr_start),
                "windowEnd": ms_to_iso(corr_end),
            },
            "correlatedRuns": [
                {
                    "runAt": run.run_at_iso,
                    "runAtMs": run.run_at_ms,
                    "jobId": run.job_id,
                    "jobName": run.job_name,
                    "durationMs": run.duration_ms,
                    "deltaFromWindowStartMs": run.run_at_ms - bucket_start,
                    "deltaFromWindowCenterMs": run.run_at_ms - window_center,
                    "sourceFile": run.source_file,
                }
                for run in correlated_runs
            ],
            "correlatedJobs": correlated_jobs,
        }
        windows.append(window)

    return windows


def default_output_paths(ts_label: str) -> tuple[Path, Path]:
    base = Path("eval/history")
    return (
        base / f"lane-hotspots-{ts_label}.json",
        base / f"lane-hotspots-{ts_label}.md",
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def fmt_job(job: dict[str, Any]) -> str:
    name = job.get("jobName") or "unknown"
    return f"{job['jobId']} ({name}) x{job['runCount']}"


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    summary = payload["summary"]
    windows = payload["windows"]
    warnings = payload["warnings"]
    generated_at = payload["generatedAt"]

    lines: list[str] = []
    lines.append("# Lane-Wait Hot Windows")
    lines.append("")
    lines.append(f"- Generated: `{generated_at}`")
    lines.append(
        f"- Lookback: `{summary['hoursAnalyzed']}h`; bucket: `{summary['bucketMinutes']}m`; "
        f"correlation: `+/-{summary['correlationWindowSeconds']}s`"
    )
    lines.append(f"- Lane events in scope: `{summary['eventsInScope']}`")
    lines.append(f"- Unique lanes: `{summary['uniqueLanes']}`")
    lines.append(f"- Cron runs in scope: `{summary['runsInScope']}`")
    lines.append(f"- Top windows returned: `{summary['topWindowsReturned']}`")
    lines.append("")

    lines.append("## Top Windows")
    lines.append("")
    lines.append(
        "| Rank | Window (UTC) | Events | Max Wait (ms) | Avg Wait (ms) | Lanes | Correlated Runs | Correlated Jobs |"
    )
    lines.append(
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    for window in windows:
        jobs_brief = ", ".join(
            f"{job['jobId']} ({job['runCount']})" for job in window["correlatedJobs"][:3]
        )
        lines.append(
            f"| {window['rank']} | {window['windowStart']} to {window['windowEnd']} | "
            f"{window['eventCount']} | {window['maxWaitMs']} | {window['avgWaitMs']} | "
            f"{len(window['lanes'])} | {len(window['correlatedRuns'])} | {jobs_brief or '-'} |"
        )

    for window in windows:
        lines.append("")
        lines.append(f"## Window #{window['rank']}: {window['windowStart']} to {window['windowEnd']}")
        lines.append("")
        lines.append(
            f"- Events: `{window['eventCount']}`; max wait: `{window['maxWaitMs']}ms`; "
            f"avg wait: `{window['avgWaitMs']}ms`"
        )
        lines.append(f"- Correlated runs: `{len(window['correlatedRuns'])}`")
        lines.append(
            f"- Correlation window: `{window['correlation']['windowStart']}` to "
            f"`{window['correlation']['windowEnd']}`"
        )
        lines.append("- Top lanes:")
        for lane in window["lanes"][:5]:
            lines.append(
                f"  - `{lane['lane']}` x{lane['count']} (max `{lane['maxWaitMs']}ms`, avg `{lane['avgWaitMs']}ms`)"
            )
        if window["correlatedJobs"]:
            lines.append("- Correlated jobs:")
            for job in window["correlatedJobs"]:
                lines.append(f"  - {fmt_job(job)}")
        else:
            lines.append("- Correlated jobs: none")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.hours <= 0:
        raise SystemExit("--hours must be > 0")
    if args.bucket_minutes <= 0:
        raise SystemExit("--bucket-minutes must be > 0")
    if args.top <= 0:
        raise SystemExit("--top must be > 0")
    if args.correlation_window_seconds < 0:
        raise SystemExit("--correlation-window-seconds must be >= 0")

    warnings: list[str] = []
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    cutoff_ms = now_ms - (args.hours * 60 * 60 * 1000)
    corr_window_ms = args.correlation_window_seconds * 1000

    lane_log_path = Path.home() / ".openclaw" / "logs" / "gateway.err.log"
    runs_dir = Path.home() / ".openclaw" / "cron" / "runs"
    jobs_path = Path.home() / ".openclaw" / "cron" / "jobs.json"

    job_names = load_job_names(jobs_path, warnings)
    lane_events = load_lane_events(lane_log_path, cutoff_ms, now_ms, warnings)
    cron_runs = load_cron_runs(runs_dir, job_names, cutoff_ms, corr_window_ms, warnings)

    windows = summarize_windows(
        events=lane_events,
        runs=cron_runs,
        bucket_minutes=args.bucket_minutes,
        top_n=args.top,
        corr_window_seconds=args.correlation_window_seconds,
    )

    ts_label = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    default_json, default_md = default_output_paths(ts_label)
    output_json = Path(args.output_json) if args.output_json else default_json
    output_md = Path(args.output_md) if args.output_md else default_md

    unique_corr_jobs = {
        run["jobId"] for window in windows for run in window["correlatedRuns"]
    }
    payload = {
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "parameters": {
            "hours": args.hours,
            "bucketMinutes": args.bucket_minutes,
            "top": args.top,
            "correlationWindowSeconds": args.correlation_window_seconds,
        },
        "sources": {
            "laneLog": str(lane_log_path),
            "cronRunsDir": str(runs_dir),
            "jobsMap": str(jobs_path),
        },
        "summary": {
            "hoursAnalyzed": args.hours,
            "bucketMinutes": args.bucket_minutes,
            "correlationWindowSeconds": args.correlation_window_seconds,
            "analysisStartMs": cutoff_ms,
            "analysisStart": ms_to_iso(cutoff_ms),
            "analysisEndMs": now_ms,
            "analysisEnd": ms_to_iso(now_ms),
            "eventsInScope": len(lane_events),
            "runsInScope": len(cron_runs),
            "uniqueLanes": len({event.lane for event in lane_events}),
            "topWindowsRequested": args.top,
            "topWindowsReturned": len(windows),
            "uniqueCorrelatedJobs": len(unique_corr_jobs),
            "warningCount": len(warnings),
        },
        "windows": windows,
        "warnings": warnings,
    }

    write_json(output_json, payload)
    write_markdown(output_md, payload)

    print(f"JSON report: {output_json}")
    print(f"Markdown report: {output_md}")
    print(
        "Summary: "
        f"events={payload['summary']['eventsInScope']}, "
        f"windows={payload['summary']['topWindowsReturned']}, "
        f"correlated_jobs={payload['summary']['uniqueCorrelatedJobs']}, "
        f"warnings={payload['summary']['warningCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
