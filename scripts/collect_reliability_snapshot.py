#!/usr/bin/env python3
"""
Collect a 24h reliability snapshot for ORION runtime and write eval artifacts.

The snapshot is used by the inbox-hardness sweep as a durable SLO input:
- queue lifecycle visibility (queued + pending_verification)
- queue age/stale drift
- jobs-state / delivery health cross-check
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


SLO_THRESHOLDS = {
    "max_queued": 160,
    "max_pending_verification": 120,
    "max_stale_ratio": 0.20,
    "max_queue_growth_ratio": 0.40,
    "max_pending_verification_share": 0.60,
}

CANONICAL_INBOX_CRON_NAME = "assistant-inbox-notify"
OBSOLETE_QUEUE_CRON_NAMES = {
    "assistant-task-loop",
    "inbox-result-notify-discord",
}


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[idx]


def _safe_float(v: object, default: float | None = None) -> float | None:
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _load_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


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


def _inbox_queue_contract(jobs_path: Path) -> dict:
    canonical_launch_agent = Path.home() / "Library" / "LaunchAgents" / "ai.orion.inbox_result_notify.plist"
    launchagent_active = canonical_launch_agent.exists()

    if not jobs_path.exists():
        if launchagent_active:
            return {
                "path": str(jobs_path),
                "status": "warn",
                "canonical_job": {
                    "name": CANONICAL_INBOX_CRON_NAME,
                    "present": False,
                    "enabled": True,
                    "sessionTarget": "launchagent",
                    "delivery_mode": "launchagent",
                },
                "legacy_queue_jobs_present": [],
                "legacy_queue_jobs_enabled": [],
                "notes": ["jobs.json missing but canonical launch agent is active"],
                "assertions": [
                    {
                        "severity": "warn",
                        "code": "jobs_json_missing",
                        "message": "jobs.json missing for inbox contract validation",
                    }
                ],
            }

        return {
            "path": str(jobs_path),
            "status": "missing",
            "canonical_job": {
                "name": CANONICAL_INBOX_CRON_NAME,
                "present": False,
                "enabled": False,
                "sessionTarget": None,
                "delivery_mode": None,
            },
            "legacy_queue_jobs_present": [],
            "legacy_queue_jobs_enabled": [],
            "notes": ["jobs file missing"],
            "assertions": [
                {
                    "severity": "fail",
                    "code": "jobs_json_missing",
                    "message": "jobs.json missing for inbox contract validation",
                }
            ],
        }

    data = json.loads(jobs_path.read_text())
    jobs = data.get("jobs", [])
    if not isinstance(jobs, list):
        jobs = []

    canonical = {
        "present": False,
        "enabled": False,
        "sessionTarget": None,
        "delivery_mode": None,
    }
    legacy_present: list[str] = []
    legacy_enabled: list[str] = []
    assertions: list[dict[str, Any]] = []

    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = str(job.get("name") or "").strip()
        if not name:
            continue

        if name == CANONICAL_INBOX_CRON_NAME:
            canonical.update(
                {
                    "present": True,
                    "enabled": bool(job.get("enabled")),
                    "sessionTarget": str(job.get("sessionTarget") or ""),
                    "delivery_mode": str((job.get("delivery") or {}).get("mode") or ""),
                }
            )

        if name in OBSOLETE_QUEUE_CRON_NAMES:
            legacy_present.append(name)
            if bool(job.get("enabled")):
                legacy_enabled.append(name)

    if not canonical["present"] and not launchagent_active:
        assertions.append(
            {
                "severity": "fail",
                "code": "canonical_inbox_job_missing",
                "message": f"canonical queue job '{CANONICAL_INBOX_CRON_NAME}' is missing",
            }
        )
    elif not canonical["enabled"] and not launchagent_active:
        assertions.append(
            {
                "severity": "warn",
                "code": "canonical_inbox_job_disabled",
                "message": f"canonical queue job '{CANONICAL_INBOX_CRON_NAME}' is present but disabled",
            }
        )

    for name in sorted(set(legacy_enabled)):
        assertions.append(
            {
                "severity": "warn",
                "code": "legacy_queue_job_enabled",
                "message": f"legacy queue job '{name}' is still enabled",
            }
        )

    status = "pass" if not assertions else "warn" if any(item["severity"] == "warn" for item in assertions) else "fail"

    if launchagent_active:
        canonical["enabled"] = True
        canonical["sessionTarget"] = "launchagent"
        canonical["delivery_mode"] = "launchagent"

    status = "pass" if not assertions else "warn" if any(item["severity"] == "warn" for item in assertions) else "fail"

    if not assertions and not canonical["enabled"] and not canonical["present"]:
        status = "warn"

    return {
        "path": str(jobs_path),
        "status": status,
        "canonical_job": {
            "name": CANONICAL_INBOX_CRON_NAME,
            **canonical,
        },
        "legacy_queue_jobs_present": sorted(set(legacy_present)),
        "legacy_queue_jobs_enabled": sorted(set(legacy_enabled)),
        "notes": [
            "legacy canonical scheduler mapping is expected to be queue-cycle driven"
            if status == "pass"
            else "scheduler cleanup needs review before operator unlock"
        ],
        "assertions": assertions,
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


def _queue_age_buckets(ages: list[float]) -> dict[str, int]:
    buckets = {"0-1h": 0, "1-4h": 0, "4-24h": 0, ">24h": 0}
    for age in ages:
        if age < 1.0:
            buckets["0-1h"] += 1
        elif age < 4.0:
            buckets["1-4h"] += 1
        elif age < 24.0:
            buckets["4-24h"] += 1
        else:
            buckets[">24h"] += 1
    return buckets


def _queue_ages(records: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None]:
    ages = [float(r.get("age_hours")) for r in records if isinstance(r.get("age_hours"), (int, float))]
    if not ages:
        return None, None, None
    return min(ages), max(ages), sum(ages) / len(ages)


def _bucket_stale(records: list[dict[str, Any]], *, state_name: str) -> dict[str, Any]:
    stale_count = 0
    missing = 0
    ages: list[float] = []
    for job in records:
        age = _safe_float(job.get("age_hours"))
        threshold = _safe_float(job.get("stale_threshold_hours"), 24.0)
        if age is None:
            missing += 1
            continue
        ages.append(age)
        if age > threshold:
            stale_count += 1
    ratio = (stale_count / len(records)) if records else 0.0
    return {
        "state": state_name,
        "count": len(records),
        "stale_count": stale_count,
        "stale_ratio": round(ratio, 4),
        "missing_age_or_threshold": missing,
        "age_min": min(ages) if ages else None,
        "age_max": max(ages) if ages else None,
        "age_mean": round(sum(ages) / len(ages), 3) if ages else None,
        "age_buckets": _queue_age_buckets(ages),
    }


def _queue_health(summary_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(summary_payload, dict):
        return {
            "status": "missing",
            "counts": {},
            "assertions": [
                {
                    "severity": "fail",
                    "code": "missing_summary",
                    "message": "tasks/JOBS/summary.json missing or invalid",
                }
            ],
        }

    jobs = summary_payload.get("jobs", [])
    if not isinstance(jobs, list):
        jobs = []

    queued = [j for j in jobs if str(j.get("state") or "").strip() == "queued"]
    pending_verification = [j for j in jobs if str(j.get("state") or "").strip() == "pending_verification"]

    queue_state = {
        "queued": _bucket_stale(queued, state_name="queued"),
        "pending_verification": _bucket_stale(
            pending_verification,
            state_name="pending_verification",
        ),
    }

    assertions: list[dict[str, Any]] = []
    for job in queued:
        if not str(job.get("queued_digest") or "").strip():
            assertions.append({
                "severity": "warn",
                "code": "queued_missing_digest",
                "job_id": str(job.get("job_id") or ""),
            })

    for job in pending_verification:
        result_status = str((job.get("result") or {}).get("status") or "").strip().lower()
        if result_status not in {"ok"}:
            assertions.append(
                {
                    "severity": "warn",
                    "code": "pending_verification_nonok_result",
                    "job_id": str(job.get("job_id") or ""),
                    "status": result_status,
                }
            )

    total_queued = len(queued)
    total_pending_verification = len(pending_verification)
    total_inflight = total_queued + total_pending_verification
    pending_share = (total_pending_verification / max(1, total_inflight))

    status = "pass"
    if total_queued > SLO_THRESHOLDS["max_queued"]:
        status = "fail"
        assertions.append(
            {
                "severity": "fail",
                "code": "queue_count_exceeds_cap",
                "observed": total_queued,
                "threshold": SLO_THRESHOLDS["max_queued"],
            }
        )

    if total_pending_verification > SLO_THRESHOLDS["max_pending_verification"]:
        if status == "pass":
            status = "warn"
        assertions.append(
            {
                "severity": "warn",
                "code": "pending_verification_count_raised",
                "observed": total_pending_verification,
                "threshold": SLO_THRESHOLDS["max_pending_verification"],
            }
        )

    if pending_share > SLO_THRESHOLDS["max_pending_verification_share"]:
        if status == "pass":
            status = "warn"
        assertions.append(
            {
                "severity": "warn",
                "code": "pending_verification_ratio_high",
                "observed": round(pending_share, 4),
                "threshold": SLO_THRESHOLDS["max_pending_verification_share"],
            }
        )

    for state_name, bucket in queue_state.items():
        if bucket["stale_ratio"] > SLO_THRESHOLDS["max_stale_ratio"]:
            if status == "pass":
                status = "warn"
            assertions.append(
                {
                    "severity": "warn",
                    "code": "stale_ratio_high",
                    "state": state_name,
                    "observed": bucket["stale_ratio"],
                    "threshold": SLO_THRESHOLDS["max_stale_ratio"],
                }
            )

    return {
        "status": status,
        "counts": {
            "queued": total_queued,
            "pending_verification": total_pending_verification,
            "total_jobs": len(jobs),
            "workflow_count": summary_payload.get("workflow_count", 0),
        },
        "age_summary": {
            "queued": _queue_ages(queued),
            "pending_verification": _queue_ages(pending_verification),
        },
        "state_buckets": queue_state,
        "assertions": assertions,
    }


def _jobs_state_health(jobs_state_path: Path) -> dict[str, Any]:
    data = _load_json(jobs_state_path, {})
    if not isinstance(data, dict):
        return {"status": "missing", "version": None, "total": 0}
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        jobs = {}
    total = len(jobs)
    by_last_status: Counter[str] = Counter()
    delivery_status: Counter[str] = Counter()
    for payload in jobs.values():
        if not isinstance(payload, dict):
            continue
        st = payload.get("state", {})
        if not isinstance(st, dict):
            continue
        if st.get("lastStatus"):
            by_last_status[str(st["lastStatus"])] += 1
        if st.get("lastDeliveryStatus"):
            delivery_status[str(st["lastDeliveryStatus"])] += 1
    return {
        "status": "ok" if total else "empty",
        "version": data.get("version"),
        "total": total,
        "by_last_status": dict(by_last_status),
        "delivery_status_counts": dict(delivery_status),
    }


def _queue_growth(*, jobs_summary_path: Path, history_dir: Path) -> dict[str, Any]:
    snapshot = _load_json(jobs_summary_path, {})
    history: list[Path] = []
    if history_dir.exists():
        history = sorted(history_dir.glob("reliability-*.json"))
    if not snapshot or not history:
        return {"previous": None, "delta": None}

    previous = _load_json(history[-1], {})
    if not isinstance(previous, dict):
        return {"previous": str(history[-1]), "delta": None}

    curr = snapshot.get("counts", {}) if isinstance(snapshot, dict) else {}
    prev = previous.get("queue", {}).get("counts", {})
    if not isinstance(prev, dict):
        prev = {}

    delta_queued = int(curr.get("queued", 0)) - int(prev.get("queued", 0))
    delta_pending = int(curr.get("pending_verification", 0)) - int(prev.get("pending_verification", 0))
    prev_total = int(prev.get("queued", 0)) + int(prev.get("pending_verification", 0))
    curr_total = int(curr.get("queued", 0)) + int(curr.get("pending_verification", 0))
    ratio = (delta_queued + delta_pending) / max(1, prev_total)

    return {
        "previous": {
            "file": str(history[-1]),
            "queued": prev.get("queued"),
            "pending_verification": prev.get("pending_verification"),
        },
        "delta": {
            "queued_delta": delta_queued,
            "pending_verification_delta": delta_pending,
        },
        "delta_total_ratio": round(ratio, 4),
        "slo_pass": abs(ratio) <= SLO_THRESHOLDS["max_queue_growth_ratio"],
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


def _slo_status(*, queue_health: dict, queue_growth: dict, inbox_contract: dict, eval_gate: dict) -> str:
    if (
        queue_health.get("status") == "pass"
        and queue_growth.get("slo_pass", True)
        and inbox_contract.get("status") == "pass"
        and eval_gate.get("status") == "pass"
    ):
        return "pass"

    if (
        queue_health.get("status") in {"warn", "fail"}
        or not queue_growth.get("slo_pass", True)
        or inbox_contract.get("status") != "pass"
        or eval_gate.get("status") != "pass"
    ):
        return "warn"

    return "pass"


def _render_md(report: dict) -> str:
    lane = report["lane_wait_24h"]
    cron = report["cron"]
    contract = report["inbox_queue_contract"]
    queue_health = report["queue_health"]
    queue = report["queue"]
    queue_growth = report["queue_growth"]
    delivery_queue = report["delivery_queue"]
    jobs_state = report["jobs_state"]
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
        "## Inbox Queue Contract",
        "",
        f"- Contract status: `{contract['status']}`",
        f"- Canonical job present: `{contract['canonical_job']['present']}`",
        f"- Canonical job enabled: `{contract['canonical_job']['enabled']}`",
        f"- Canonical session target: `{contract['canonical_job']['sessionTarget']}`",
        f"- Canonical delivery mode: `{contract['canonical_job']['delivery_mode']}`",
        f"- Legacy queue jobs present: `{contract['legacy_queue_jobs_present']}`",
        f"- Legacy queue jobs enabled: `{contract['legacy_queue_jobs_enabled']}`",
        f"- Contract assertions: `{contract['assertions']}`",
        "",
        "## Job State (`jobs-state.json`)",
        "",
        f"- Version: `{jobs_state.get('version', 'n/a')}`",
        f"- Total: `{jobs_state.get('total', 0)}`",
        f"- By last status: `{jobs_state.get('by_last_status', {})}`",
        f"- Delivery status counts: `{jobs_state.get('delivery_status_counts', {})}`",
        "",
        "## Queue Health",
        "",
        f"- Status: `{queue_health['status']}`",
        f"- Queued: `{queue_health['counts']['queued']}`",
        f"- Pending verification: `{queue_health['counts']['pending_verification']}`",
        f"- Age buckets: `{queue_health['state_buckets']}`",
        f"- Assertions: `{queue_health['assertions']}`",
        f"- Growth: `{queue_growth}`",
        "",
        "## Delivery Queue",
        "",
        f"- Files: `{delivery_queue['files']}`",
        f"- By channel: `{delivery_queue['by_channel']}`",
        f"- Top errors: `{delivery_queue['top_errors']}`",
        "",
        "## Eval Gate",
        "",
        f"- Status: `{gate['status']}`",
        f"- Reasons: `{gate['reasons']}`",
        "",
        "## Queue Snapshot",
        "",
        f"- Source: `{queue['path']}`",
        f"- Counts: `{queue['counts']}`",
        f"- Workflow count: `{queue['counts'].get('workflow_count')}`",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect ORION reliability snapshot artifacts.")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--log-path", default="~/.openclaw/logs/gateway.err.log")
    ap.add_argument("--jobs-path", default="~/.openclaw/cron/jobs.json")
    ap.add_argument("--jobs-state-path", default="~/.openclaw/cron/jobs-state.json")
    ap.add_argument("--jobs-summary-path", default="tasks/JOBS/summary.json")
    ap.add_argument("--queue-dir", default="~/.openclaw/delivery-queue")
    ap.add_argument("--eval-compare", default="eval/latest_compare.json")
    ap.add_argument("--history-dir", default="eval/history")
    ap.add_argument("--output-json", default=None)
    ap.add_argument("--output-md", default="eval/reliability-latest.md")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    output_json = Path(args.output_json) if args.output_json else Path(f"eval/history/reliability-{ts}.json")
    output_md = Path(args.output_md)

    jobs_summary_path = Path(args.jobs_summary_path).expanduser()
    queue_summary = _load_json(jobs_summary_path, {})
    queue_health = _queue_health(queue_summary if isinstance(queue_summary, dict) else None)
    inbox_contract = _inbox_queue_contract(Path(args.jobs_path).expanduser())
    queue_growth = _queue_growth(
        jobs_summary_path=jobs_summary_path,
        history_dir=Path(args.history_dir).expanduser(),
    )

    eval_gate = _eval_gate(Path(args.eval_compare))
    report = {
        "kind": "reliability_snapshot",
        "generated_at": now.isoformat(),
        "lane_wait_24h": _parse_lane_waits(Path(args.log_path).expanduser(), args.hours),
        "cron": _cron_stats(Path(args.jobs_path).expanduser()),
        "jobs_state": _jobs_state_health(Path(args.jobs_state_path).expanduser()),
        "inbox_queue_contract": inbox_contract,
        "queue_health": queue_health,
        "queue": {
            "path": str(jobs_summary_path),
            "counts": queue_health.get("counts", {}),
            "state_buckets": queue_health.get("state_buckets", {}),
        },
        "queue_growth": queue_growth,
        "delivery_queue": _delivery_queue(Path(args.queue_dir).expanduser()),
        "eval_gate": eval_gate,
        "slo": {
            "max_queued": SLO_THRESHOLDS["max_queued"],
            "max_pending_verification": SLO_THRESHOLDS["max_pending_verification"],
            "max_stale_ratio": SLO_THRESHOLDS["max_stale_ratio"],
            "max_queue_growth_ratio": SLO_THRESHOLDS["max_queue_growth_ratio"],
            "max_pending_verification_share": SLO_THRESHOLDS["max_pending_verification_share"],
            "status": _slo_status(
                queue_health=queue_health,
                queue_growth=queue_growth,
                inbox_contract=inbox_contract,
                eval_gate=eval_gate,
            ),
        },
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
    print(f"queue_queued: {queue_health['counts'].get('queued', 0)}")
    print(f"queue_pending_verification: {queue_health['counts'].get('pending_verification', 0)}")
    print(f"eval_gate: {report['eval_gate']['status']}")
    print(f"slo_status: {report['slo']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
