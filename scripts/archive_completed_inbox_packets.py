#!/usr/bin/env python3
"""Archive closed inbox packets after their result notification has aged out."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

try:
    from inbox_file_ops import atomic_write_text
    from inbox_state import sha256_lines
except Exception:  # pragma: no cover
    from scripts.inbox_file_ops import atomic_write_text  # type: ignore
    from scripts.inbox_state import sha256_lines  # type: ignore


def _split_packets(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    starts = [idx for idx, line in enumerate(lines) if line.strip() == "TASK_PACKET v1"]
    return [(start, starts[i + 1] if i + 1 < len(starts) else len(lines), lines[start : starts[i + 1] if i + 1 < len(starts) else len(lines)]) for i, start in enumerate(starts)]


def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in packet_lines:
        if line.strip() == "Result:":
            break
        out.append(line)
    return out


def _load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _result_delivery_ts(job: dict) -> float | None:
    delivery = job.get("notification_delivery")
    if not isinstance(delivery, dict):
        return None
    result = delivery.get("result")
    if not isinstance(result, dict):
        return None
    if str(result.get("status") or "") not in {"delivered", "suppressed", "failed-to-deliver"}:
        return None
    channels = result.get("channels")
    if not isinstance(channels, dict):
        return None
    stamps: list[float] = []
    for payload in channels.values():
        if not isinstance(payload, dict):
            continue
        if str(payload.get("status") or "") not in {"delivered", "suppressed", "failed-to-deliver"}:
            continue
        ts = payload.get("last_ts")
        if isinstance(ts, (int, float)):
            stamps.append(float(ts))
    return max(stamps) if stamps else None


def _eligible_jobs(summary: dict, *, now_ts: float, older_than_hours: float) -> dict[tuple[str, str], dict]:
    cutoff = now_ts - max(0.1, older_than_hours) * 3600.0
    out: dict[tuple[str, str], dict] = {}
    jobs = summary.get("jobs", [])
    if not isinstance(jobs, list):
        return out
    for job in jobs:
        if not isinstance(job, dict):
            continue
        result = job.get("result")
        if not isinstance(result, dict):
            continue
        state = str(job.get("state") or "")
        result_status = str(result.get("status") or "").lower()
        if state == "complete" and result_status == "ok":
            pass
        elif state == "cancelled" and result_status == "cancelled":
            pass
        else:
            continue
        notified_at = _result_delivery_ts(job)
        if notified_at is None or notified_at > cutoff:
            continue
        inbox = job.get("inbox")
        if not isinstance(inbox, dict):
            continue
        path = str(inbox.get("path") or "").strip()
        digest = str(job.get("queued_digest") or "").strip()
        if path and digest:
            out[(path, digest)] = job
    return out


def archive_completed_packets(
    *,
    repo_root: Path,
    older_than_hours: float,
    apply: bool,
    now_ts: float | None = None,
) -> dict[str, object]:
    now = float(now_ts if now_ts is not None else time.time())
    summary = _load_json(repo_root / "tasks" / "JOBS" / "summary.json")
    eligible = _eligible_jobs(summary, now_ts=now, older_than_hours=older_than_hours)
    inbox_dir = repo_root / "tasks" / "INBOX"
    archive_path = inbox_dir / "archive" / f"completed_{time.strftime('%Y%m%d', time.localtime(now))}.md"
    archived: list[dict[str, object]] = []
    archive_blocks: list[str] = []

    for inbox_path in sorted(inbox_dir.glob("*.md")):
        if inbox_path.name.upper() == "README.MD":
            continue
        rel = str(inbox_path.relative_to(repo_root))
        lines = inbox_path.read_text(encoding="utf-8").splitlines()
        blocks = _split_packets(lines)
        if not blocks:
            continue

        out_lines: list[str] = []
        cursor = 0
        changed = False
        for start, end, block in blocks:
            digest = sha256_lines(_packet_before_result(block))
            job = eligible.get((rel, digest))
            if job is None:
                out_lines.extend(lines[cursor:end])
                cursor = end
                continue
            changed = True
            out_lines.extend(lines[cursor:start])
            archived.append(
                {
                    "path": rel,
                    "line": start + 1,
                    "owner": job.get("owner"),
                    "objective": job.get("objective"),
                    "queued_digest": digest,
                }
            )
            archive_blocks.append("")
            archive_blocks.append(f"## Source: {rel}:{start + 1}")
            archive_blocks.extend(block)
            cursor = end

        out_lines.extend(lines[cursor:])
        if apply and changed:
            atomic_write_text(inbox_path, "\n".join(out_lines).rstrip() + "\n")

    if apply and archive_blocks:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        existing = archive_path.read_text(encoding="utf-8").splitlines() if archive_path.exists() else ["# Archived Completed Task Packets"]
        content = "\n".join(existing + archive_blocks).rstrip() + "\n"
        atomic_write_text(archive_path, content)

    return {
        "mode": "apply" if apply else "dry-run",
        "older_than_hours": older_than_hours,
        "archive_path": str(archive_path),
        "archived_count": len(archived),
        "archived": archived,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive closed Task Packet blocks from active inbox files.")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--older-than-hours", type=float, default=48.0)
    ap.add_argument("--apply", action="store_true", help="Actually move packet blocks; default is dry-run.")
    ap.add_argument("--json", action="store_true", help="Print JSON output.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    result = archive_completed_packets(
        repo_root=repo_root,
        older_than_hours=max(0.1, float(args.older_than_hours)),
        apply=bool(args.apply),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"ARCHIVE_COMPLETED mode={result['mode']} archived={result['archived_count']} "
            f"older_than_hours={result['older_than_hours']} archive={result['archive_path']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
