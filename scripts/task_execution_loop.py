#!/usr/bin/env python3
"""
Closed-loop execution guard for Task Packets + ticket lanes.

Why this exists:
- Keep tasks/NOTES/{status,plan}.md continuously updated from actual repo state.
- Reconcile safe drift between ticket lane and Status field.
- Reconcile packet lifecycle with ticket lanes:
  - pending packet with ticket reference -> ticket should be in-progress
  - terminal packet result with ticket reference -> ticket should be testing
- Fail loudly for stale pending packets when strict mode is enabled.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import os
import re
import time
from pathlib import Path

try:
    from inbox_state import load_kv_state, save_kv_state, sha256_lines
except Exception:  # pragma: no cover
    from scripts.inbox_state import load_kv_state, save_kv_state, sha256_lines  # type: ignore


LANES = ("backlog", "in-progress", "testing", "done")
LANE_TO_STATUS = {
    "backlog": "queued",
    "in-progress": "in-progress",
    "testing": "testing",
    "done": "done",
}

RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")
RE_RESULT_STATUS = re.compile(r"^\s*-?\s*Status:\s*(OK|FAILED|BLOCKED)\b", re.IGNORECASE)
RE_TICKET_PATH = re.compile(r"(tasks/WORK/(?:backlog|in-progress|testing|done)/\d{4}-[a-z0-9][a-z0-9-]*\.md)")


@dataclasses.dataclass
class Ticket:
    path: Path
    relpath: str
    lane: str
    filename: str
    status: str
    title: str


@dataclasses.dataclass
class Packet:
    inbox_path: Path
    display_path: str
    start_line: int
    fields: dict[str, str]
    lines: list[str]
    pending_key: str
    result_status: str | None
    ticket_refs: list[str]


@dataclasses.dataclass
class Action:
    kind: str
    ticket: str
    detail: str


def _split_packets(lines: list[str], *, start_line_offset: int = 0) -> list[tuple[int, list[str]]]:
    """Return (start_line_number, packet_lines) list for TASK_PACKET v1 blocks."""
    packets: list[tuple[int, list[str]]] = []
    in_fence = False
    cur: list[str] | None = None
    cur_start: int | None = None

    for idx, raw in enumerate(lines, start=1 + start_line_offset):
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_fence = not in_fence

        if not in_fence and RE_PACKET_HEADER.match(line):
            if cur is not None and cur_start is not None:
                packets.append((cur_start, cur))
            cur = [line]
            cur_start = idx
            continue

        if cur is not None:
            cur.append(line)

    if cur is not None and cur_start is not None:
        packets.append((cur_start, cur))

    return packets


def _packet_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in packet_lines[1:]:
        m = RE_KV.match(line)
        if not m:
            continue
        fields[m.group("key").strip()] = m.group("value").strip()
    return fields


def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in packet_lines:
        if ln.strip() == "Result:":
            break
        out.append(ln)
    return out


def _packet_result_status(packet_lines: list[str]) -> str | None:
    in_result = False
    for ln in packet_lines:
        s = ln.rstrip("\n")
        if s.strip() == "Result:":
            in_result = True
            continue
        if not in_result:
            continue
        m = RE_RESULT_STATUS.match(s.strip())
        if m:
            return m.group(1).upper()
    return None


def _extract_ticket_refs(packet_lines: list[str]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for ln in packet_lines:
        for m in RE_TICKET_PATH.finditer(ln):
            ref = m.group(1)
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _parse_ticket(path: Path, repo_root: Path, lane: str) -> Ticket:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = path.stem
    status = ""

    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip() or title
            break

    for ln in lines:
        if ln.startswith("Status:"):
            status = ln.split(":", 1)[1].strip()
            break

    return Ticket(
        path=path,
        relpath=str(path.relative_to(repo_root)),
        lane=lane,
        filename=path.name,
        status=status,
        title=title,
    )


def _load_tickets(repo_root: Path) -> dict[str, Ticket]:
    by_name: dict[str, Ticket] = {}
    for lane in LANES:
        lane_dir = repo_root / "tasks" / "WORK" / lane
        if not lane_dir.exists():
            continue
        for p in sorted(lane_dir.glob("*.md")):
            m = re.match(r"^\d{4}-[a-z0-9][a-z0-9-]*\.md$", p.name)
            if not m:
                continue
            t = _parse_ticket(p, repo_root, lane)
            by_name[t.filename] = t
    return by_name


def _load_packets(repo_root: Path) -> list[Packet]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    out: list[Packet] = []
    if not inbox_dir.exists():
        return out

    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue

        text = inbox.read_text(encoding="utf-8")
        all_lines = text.splitlines()

        packets_header_idx = None
        for i, line in enumerate(all_lines):
            if line.strip() == "## Packets":
                packets_header_idx = i
                break

        start_idx = packets_header_idx + 1 if packets_header_idx is not None else 0
        packet_blocks = _split_packets(all_lines[start_idx:], start_line_offset=start_idx)

        try:
            display = str(inbox.relative_to(repo_root))
        except Exception:
            display = inbox.resolve().as_posix()

        for start_line, pkt_lines in packet_blocks:
            before = _packet_before_result(pkt_lines)
            fp = sha256_lines(before)
            result_status = _packet_result_status(pkt_lines)
            out.append(
                Packet(
                    inbox_path=inbox,
                    display_path=display,
                    start_line=start_line,
                    fields=_packet_fields(pkt_lines),
                    lines=pkt_lines,
                    pending_key=f"pending:{fp}",
                    result_status=result_status,
                    ticket_refs=_extract_ticket_refs(pkt_lines),
                )
            )

    return out


def _rewrite_status(md: str, new_status: str) -> str:
    lines = md.splitlines()
    kept = [ln for ln in lines if not ln.startswith("Status:")]
    insert = f"Status: {new_status}"

    for i, ln in enumerate(kept):
        if ln.startswith("Owner:"):
            kept.insert(i + 1, insert)
            return "\n".join(kept).rstrip() + "\n"

    for i, ln in enumerate(kept):
        if ln.startswith("# "):
            kept.insert(i + 1, "")
            kept.insert(i + 2, insert)
            return "\n".join(kept).rstrip() + "\n"

    return (insert + "\n\n" + "\n".join(kept)).rstrip() + "\n"


def _append_note(md: str, note: str) -> str:
    if "## Notes" in md:
        head, tail = md.split("## Notes", 1)
        tail = tail.lstrip("\n")
        return f"{head}## Notes\n- {note}\n{tail}"
    return md.rstrip() + f"\n\n## Notes\n- {note}\n"


def _update_ticket_status(ticket: Ticket, new_status: str) -> None:
    raw = ticket.path.read_text(encoding="utf-8")
    out = _rewrite_status(raw, new_status)
    if out != raw:
        ticket.path.write_text(out, encoding="utf-8")
    ticket.status = new_status


def _move_ticket_lane(
    *, repo_root: Path, ticket: Ticket, to_lane: str, reason: str
) -> Ticket:
    if ticket.lane == to_lane:
        expected = LANE_TO_STATUS[to_lane]
        if ticket.status != expected:
            _update_ticket_status(ticket, expected)
        return ticket

    dest_dir = repo_root / "tasks" / "WORK" / to_lane
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / ticket.filename

    raw = ticket.path.read_text(encoding="utf-8")
    out = _rewrite_status(raw, LANE_TO_STATUS[to_lane])
    today = dt.datetime.now().strftime("%Y-%m-%d")
    out = _append_note(out, f"{today}: moved to {to_lane} ({reason})")
    ticket.path.write_text(out, encoding="utf-8")
    ticket.path.rename(dest)

    new_ticket = _parse_ticket(dest, repo_root, to_lane)
    return new_ticket


def _write_status_md(
    *,
    repo_root: Path,
    now_local: dt.datetime,
    lane_counts: dict[str, int],
    pending_packets: list[Packet],
    terminal_packets: list[Packet],
    stale_pending: list[tuple[Packet, float]],
    actions: list[Action],
    stale_hours: float,
) -> None:
    p = repo_root / "tasks" / "NOTES" / "status.md"
    p.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Status")
    lines.append("")
    lines.append(f"- Updated: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(
        "- Ticket lanes: "
        + " | ".join(f"{lane}={lane_counts.get(lane, 0)}" for lane in LANES)
    )
    lines.append(
        f"- Inbox packets: pending={len(pending_packets)} terminal={len(terminal_packets)}"
    )
    lines.append(
        f"- Stale pending (>{stale_hours:.1f}h): {len(stale_pending)}"
    )
    lines.append("")

    lines.append("## Stale Pending Packets")
    if stale_pending:
        for pkt, age_h in stale_pending[:20]:
            owner = pkt.fields.get("Owner", pkt.inbox_path.stem.upper())
            objective = pkt.fields.get("Objective", "(no objective)")
            lines.append(
                f"- [{owner}] {objective} ({pkt.display_path}:{pkt.start_line}, age={age_h:.1f}h)"
            )
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Reconcile Actions")
    if actions:
        for a in actions[:50]:
            lines.append(f"- {a.kind}: {a.ticket} ({a.detail})")
    else:
        lines.append("- none")
    lines.append("")

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_plan_md(
    *,
    repo_root: Path,
    now_local: dt.datetime,
    tickets: dict[str, Ticket],
    stale_pending: list[tuple[Packet, float]],
) -> None:
    p = repo_root / "tasks" / "NOTES" / "plan.md"
    p.parent.mkdir(parents=True, exist_ok=True)

    in_progress = sorted([t for t in tickets.values() if t.lane == "in-progress"], key=lambda x: x.filename)
    backlog = sorted([t for t in tickets.values() if t.lane == "backlog"], key=lambda x: x.filename)

    lines: list[str] = []
    lines.append("# Plan")
    lines.append("")
    lines.append(f"- Refreshed: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append("")

    lines.append("## Active")
    if in_progress:
        for t in in_progress[:10]:
            lines.append(f"- Continue {t.filename} ({t.title})")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Queue")
    if backlog:
        for t in backlog[:10]:
            lines.append(f"- Next {t.filename} ({t.title})")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Attention")
    if stale_pending:
        for pkt, age_h in stale_pending[:10]:
            owner = pkt.fields.get("Owner", pkt.inbox_path.stem.upper())
            objective = pkt.fields.get("Objective", "(no objective)")
            lines.append(
                f"- Resolve stale packet [{owner}] {objective} ({pkt.display_path}:{pkt.start_line}, age={age_h:.1f}h)"
            )
    else:
        lines.append("- none")
    lines.append("")

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run(
    repo_root: Path,
    *,
    apply_changes: bool,
    stale_hours: float,
    strict_stale: bool,
    state_path: Path,
) -> int:
    now_ts = time.time()
    now_local = dt.datetime.now().astimezone()

    tickets = _load_tickets(repo_root)
    packets = _load_packets(repo_root)

    pending_packets = [p for p in packets if p.result_status is None]
    terminal_packets = [p for p in packets if p.result_status is not None]

    state = load_kv_state(state_path)

    # Track first-seen timestamps for pending packets.
    pending_keys = {p.pending_key for p in pending_packets}
    for pkt in pending_packets:
        if pkt.pending_key not in state:
            state[pkt.pending_key] = now_ts

    # Clean up resolved pending keys.
    for key in list(state.keys()):
        if not key.startswith("pending:"):
            continue
        if key not in pending_keys:
            del state[key]

    stale_pending: list[tuple[Packet, float]] = []
    for pkt in pending_packets:
        started = state.get(pkt.pending_key, now_ts)
        age_h = max(0.0, (now_ts - started) / 3600.0)
        if age_h > stale_hours:
            stale_pending.append((pkt, age_h))

    actions: list[Action] = []

    # Status reconciliation from lane -> Status field.
    for t in sorted(tickets.values(), key=lambda x: x.filename):
        expected = LANE_TO_STATUS[t.lane]
        if t.status != expected:
            actions.append(Action(kind="status-sync", ticket=t.filename, detail=f"{t.status or '(missing)'} -> {expected}"))
            if apply_changes:
                _update_ticket_status(t, expected)

    # Build desired lane state from packet lifecycle.
    desired_lanes: dict[str, tuple[str, str]] = {}

    for pkt in terminal_packets:
        for ref in pkt.ticket_refs:
            base = os.path.basename(ref)
            if base in tickets:
                desired_lanes.setdefault(base, ("testing", f"terminal result in {pkt.display_path}:{pkt.start_line}"))

    for pkt in pending_packets:
        for ref in pkt.ticket_refs:
            base = os.path.basename(ref)
            if base in tickets:
                desired_lanes[base] = ("in-progress", f"pending packet in {pkt.display_path}:{pkt.start_line}")

    for filename, (target_lane, reason) in sorted(desired_lanes.items()):
        t = tickets.get(filename)
        if not t:
            continue
        if t.lane == target_lane:
            continue
        # Safe reconcile policy: only move backlog/in-progress/testing between active lanes.
        # Do not auto-reopen done tickets.
        if t.lane == "done":
            continue

        actions.append(Action(kind="lane-move", ticket=t.filename, detail=f"{t.lane} -> {target_lane}; {reason}"))
        if apply_changes:
            moved = _move_ticket_lane(repo_root=repo_root, ticket=t, to_lane=target_lane, reason=reason)
            tickets[filename] = moved

    # Write notes after reconcile pass.
    lane_counts = {lane: 0 for lane in LANES}
    for t in tickets.values():
        lane_counts[t.lane] += 1

    _write_status_md(
        repo_root=repo_root,
        now_local=now_local,
        lane_counts=lane_counts,
        pending_packets=pending_packets,
        terminal_packets=terminal_packets,
        stale_pending=sorted(stale_pending, key=lambda x: x[1], reverse=True),
        actions=actions,
        stale_hours=stale_hours,
    )
    _write_plan_md(
        repo_root=repo_root,
        now_local=now_local,
        tickets=tickets,
        stale_pending=sorted(stale_pending, key=lambda x: x[1], reverse=True),
    )

    # Bound state size.
    if len(state) > 5000:
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:4000])
    save_kv_state(state_path, state)

    stale_count = len(stale_pending)
    action_count = len(actions)
    if strict_stale and stale_count > 0:
        print(f"TASK_LOOP_STALE stale={stale_count} actions={action_count} apply={int(apply_changes)}")
        return 2

    print(f"TASK_LOOP_OK stale={stale_count} actions={action_count} apply={int(apply_changes)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Closed-loop reconcile for inbox packets, ticket lanes, and notes.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--state-path",
        default="tmp/task_execution_loop_state.json",
        help="State file path (default: tmp/task_execution_loop_state.json)",
    )
    ap.add_argument("--stale-hours", type=float, default=24.0, help="Pending-packet stale threshold in hours.")
    ap.add_argument("--strict-stale", action="store_true", help="Exit non-zero when stale pending packets exist.")
    ap.add_argument("--apply", action="store_true", help="Apply status/lane reconciliation changes.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    return run(
        repo_root,
        apply_changes=bool(args.apply),
        stale_hours=max(0.1, float(args.stale_hours)),
        strict_stale=bool(args.strict_stale),
        state_path=state_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
