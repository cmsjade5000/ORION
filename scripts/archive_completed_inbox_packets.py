#!/usr/bin/env python3
"""Archive terminal Task Packet blocks out of the active inbox files."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from inbox_state import load_kv_state
except Exception:  # pragma: no cover
    from scripts.inbox_state import load_kv_state  # type: ignore


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")


@dataclass(frozen=True)
class Candidate:
    job_id: str
    path: Path
    display_path: str
    line: int
    reason: str
    digest: str
    notify_channels: tuple[str, ...]
    eligible_ts: float | None


@dataclass(frozen=True)
class PacketBlock:
    start_line: int
    start_idx: int
    end_idx: int
    lines: list[str]


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _split_packets(lines: list[str]) -> list[PacketBlock]:
    starts: list[int] = []
    in_fence = False
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and RE_PACKET_HEADER.match(line):
            starts.append(idx)

    blocks: list[PacketBlock] = []
    for pos, start_idx in enumerate(starts):
        end_idx = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        blocks.append(
            PacketBlock(
                start_line=start_idx + 1,
                start_idx=start_idx,
                end_idx=end_idx,
                lines=lines[start_idx:end_idx],
            )
        )
    return blocks


def _delivery_ts(state: dict[str, float], *, digest: str, channels: tuple[str, ...]) -> float | None:
    if not digest:
        return None
    hits: list[float] = []
    for key, ts in state.items():
        if not key.endswith(digest):
            continue
        if ":result:" in key or key in {digest, f"telegram:{digest}"}:
            if not channels or any(key.startswith(f"{channel}:") for channel in channels) or key in {digest, f"telegram:{digest}"}:
                hits.append(float(ts))
    return max(hits) if hits else None


def _candidate_from_job(repo_root: Path, job: dict[str, object], state: dict[str, float], *, include_result_ok: bool) -> Candidate | None:
    inbox = job.get("inbox")
    if not isinstance(inbox, dict):
        return None
    display_path = str(inbox.get("path") or "").strip()
    line = int(inbox.get("line") or 0)
    if not display_path or line <= 0:
        return None

    result = job.get("result")
    result = result if isinstance(result, dict) else {}
    result_status = str(result.get("status") or "").strip().lower()
    state_name = str(job.get("state") or "").strip().lower()
    reason = ""
    if state_name == "complete":
        reason = "state_complete"
    elif include_result_ok and result_status == "ok":
        reason = "result_ok"
    else:
        return None

    channels = tuple(
        sorted(str(channel).strip().lower() for channel in job.get("notify_channels", []) if str(channel).strip())
    ) if isinstance(job.get("notify_channels"), list) else ()
    digest = str(job.get("result_digest") or "").strip()
    path = (repo_root / display_path).resolve()
    eligible_ts = _delivery_ts(state, digest=digest, channels=channels)
    if eligible_ts is None and path.exists():
        eligible_ts = path.stat().st_mtime

    return Candidate(
        job_id=str(job.get("job_id") or "").strip(),
        path=path,
        display_path=display_path,
        line=line,
        reason=reason,
        digest=digest,
        notify_channels=channels,
        eligible_ts=eligible_ts,
    )


def find_candidates(
    repo_root: Path,
    *,
    state_path: Path,
    min_age_hours: float,
    include_result_ok: bool,
    now_ts: float | None = None,
) -> list[Candidate]:
    now = time.time() if now_ts is None else now_ts
    summary = _read_json(repo_root / "tasks" / "JOBS" / "summary.json")
    state = load_kv_state(state_path)
    jobs = summary.get("jobs", [])
    if not isinstance(jobs, list):
        return []

    out: list[Candidate] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        candidate = _candidate_from_job(repo_root, item, state, include_result_ok=include_result_ok)
        if candidate is None:
            continue
        age_hours = ((now - candidate.eligible_ts) / 3600.0) if candidate.eligible_ts is not None else 0.0
        if age_hours < min_age_hours:
            continue
        out.append(candidate)
    return out


def archive_candidates(repo_root: Path, candidates: list[Candidate], *, apply: bool) -> dict[str, object]:
    archive_root = repo_root / "tasks" / "INBOX" / "archive" / time.strftime("%Y-%m-%d")
    by_path: dict[Path, list[Candidate]] = {}
    for candidate in candidates:
        by_path.setdefault(candidate.path, []).append(candidate)

    archived: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for path, path_candidates in sorted(by_path.items(), key=lambda item: item[0].as_posix()):
        if not path.exists():
            skipped.extend({"path": c.display_path, "line": c.line, "reason": "missing_file"} for c in path_candidates)
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        blocks = {block.start_line: block for block in _split_packets(lines)}
        remove_lines = {candidate.line for candidate in path_candidates}
        matched = [blocks[line] for line in sorted(remove_lines) if line in blocks]
        skipped.extend(
            {"path": c.display_path, "line": c.line, "reason": "packet_not_found"}
            for c in path_candidates
            if c.line not in blocks
        )
        if not matched:
            continue

        archive_chunks: list[str] = []
        for block in matched:
            candidate = next(c for c in path_candidates if c.line == block.start_line)
            archive_chunks.extend(
                [
                    f"<!-- archived_from: {candidate.display_path}:{candidate.line} -->",
                    f"<!-- archive_reason: {candidate.reason} -->",
                    "",
                    *block.lines,
                    "",
                ]
            )
            archived.append({"path": candidate.display_path, "line": candidate.line, "reason": candidate.reason})

        if not apply:
            continue

        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / path.name
        existing = archive_path.read_text(encoding="utf-8").splitlines() if archive_path.exists() else []
        archive_path.write_text("\n".join(existing + archive_chunks).rstrip() + "\n", encoding="utf-8")

        remove_ranges = [(block.start_idx, block.end_idx) for block in matched]
        kept: list[str] = []
        for idx, line in enumerate(lines):
            if any(start <= idx < end for start, end in remove_ranges):
                continue
            kept.append(line)
        path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")

    return {"archived": archived, "skipped": skipped, "apply": apply}


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive completed inbox Task Packet blocks.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--state-path", default="tmp/inbox_notify_state.json", help="Notifier state path.")
    ap.add_argument("--min-age-hours", type=float, default=48.0, help="Minimum completion age before archive.")
    ap.add_argument(
        "--include-result-ok",
        action="store_true",
        help="Also archive Result: Status OK packets that are still pending verification.",
    )
    ap.add_argument("--apply", action="store_true", help="Apply archive changes. Omit for dry-run.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    candidates = find_candidates(
        repo_root,
        state_path=state_path,
        min_age_hours=max(0.0, float(args.min_age_hours)),
        include_result_ok=bool(args.include_result_ok),
    )
    result = archive_candidates(repo_root, candidates, apply=bool(args.apply))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
