#!/usr/bin/env python3
"""
Shared helpers for ORION's admin-copilot scripts.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")
TICKET_RE = re.compile(r"^(?P<num>\d{4})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")
RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")


@dataclass(frozen=True)
class Ticket:
    path: Path
    lane: str
    title: str
    status: str
    notes: list[str]


@dataclass(frozen=True)
class Packet:
    inbox_path: Path
    start_line: int
    fields: dict[str, str]
    result_status: str | None


def repo_root(path: str | None = None) -> Path:
    if path:
        return Path(path).resolve()
    return Path(__file__).resolve().parents[1]


def now_et() -> dt.datetime:
    return dt.datetime.now(tz=ET)


def today_et() -> str:
    return now_et().date().isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def env_or_default(name: str, fallback: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else fallback


def load_fixture_json(env_name: str) -> Any | None:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return None
    return read_json(Path(raw).expanduser())


def run_json_command(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 20) -> Any | None:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_ticket(path: Path, lane: str) -> Ticket:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = path.stem
    status = ""
    notes: list[str] = []
    in_notes = False

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip() or title
        elif line.startswith("Status:"):
            status = line.split(":", 1)[1].strip()
        elif line.strip() == "## Notes":
            in_notes = True
            continue
        elif line.startswith("## "):
            in_notes = False

        if in_notes and line.strip().startswith("- "):
            notes.append(line.strip()[2:].strip())

    return Ticket(path=path, lane=lane, title=title, status=status, notes=notes)


def load_tickets(root: Path) -> list[Ticket]:
    tickets: list[Ticket] = []
    for lane in ("backlog", "in-progress", "testing", "done"):
        lane_dir = root / "tasks" / "WORK" / lane
        if not lane_dir.exists():
            continue
        for path in sorted(lane_dir.glob("*.md")):
            if not TICKET_RE.match(path.name):
                continue
            tickets.append(_parse_ticket(path, lane))
    return tickets


def _split_packets(lines: list[str], start_line_offset: int) -> list[tuple[int, list[str]]]:
    packets: list[tuple[int, list[str]]] = []
    in_fence = False
    current: list[str] | None = None
    current_start: int | None = None

    for idx, raw in enumerate(lines, start=1 + start_line_offset):
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_fence = not in_fence

        if not in_fence and RE_PACKET_HEADER.match(line):
            if current is not None and current_start is not None:
                packets.append((current_start, current))
            current = [line]
            current_start = idx
            continue

        if current is not None:
            current.append(line)

    if current is not None and current_start is not None:
        packets.append((current_start, current))

    return packets


def _parse_packet_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in packet_lines[1:]:
        match = RE_KV.match(line)
        if match:
            fields[match.group("key").strip()] = match.group("value").strip()
    return fields


def _packet_result_status(packet_lines: list[str]) -> str | None:
    in_result = False
    for line in packet_lines:
        if line.strip() == "Result:":
            in_result = True
            continue
        if not in_result:
            continue
        match = re.match(r"^\s*-?\s*Status:\s*(OK|FAILED|BLOCKED)\b", line.strip(), flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def load_packets(root: Path, *, owner: str | None = None) -> list[Packet]:
    inbox_dir = root / "tasks" / "INBOX"
    packets: list[Packet] = []
    if not inbox_dir.exists():
        return packets

    for inbox_path in sorted(inbox_dir.glob("*.md")):
        if inbox_path.name.upper() == "README.MD":
            continue
        lines = inbox_path.read_text(encoding="utf-8").splitlines()
        packets_header_idx = 0
        for idx, line in enumerate(lines):
            if line.strip() == "## Packets":
                packets_header_idx = idx + 1
                break
        for start_line, packet_lines in _split_packets(lines[packets_header_idx:], packets_header_idx):
            fields = _parse_packet_fields(packet_lines)
            if owner and fields.get("Owner", "").strip().upper() != owner.upper():
                continue
            packets.append(
                Packet(
                    inbox_path=inbox_path,
                    start_line=start_line,
                    fields=fields,
                    result_status=_packet_result_status(packet_lines),
                )
            )
    return packets


def extract_followup_lines(tickets: list[Ticket]) -> list[str]:
    hits: list[str] = []
    keywords = ("follow-up", "follow up", "waiting", "blocked", "awaiting")
    for ticket in tickets:
        if ticket.lane == "done":
            continue
        joined = " ".join(ticket.notes).lower()
        if any(keyword in joined for keyword in keywords):
            hits.append(f"{ticket.title} ({ticket.lane})")
    return hits


def load_calendar_events(root: Path) -> dict[str, Any]:
    fixture = load_fixture_json("ORION_ASSISTANT_CALENDAR_JSON")
    if fixture is not None:
        return fixture if isinstance(fixture, dict) else {"enabled": False, "events": []}

    names = env_or_default("ORION_ASSISTANT_CALENDAR_NAMES", "Work,Events,Birthdays")
    payload = run_json_command(
        ["bash", "scripts/calendar_events_fetch.sh"],
        cwd=root,
        env={
            "CAL_NAMES": names,
            "CAL_WINDOW_HOURS": env_or_default("ORION_ASSISTANT_CALENDAR_WINDOW_HOURS", "24"),
            "CAL_INCLUDE_ALLDAY": env_or_default("ORION_ASSISTANT_CALENDAR_INCLUDE_ALLDAY", "1"),
        },
    )
    return payload if isinstance(payload, dict) else {"enabled": False, "events": []}


def load_reminders(root: Path) -> list[dict[str, Any]]:
    fixture = load_fixture_json("ORION_ASSISTANT_REMINDERS_JSON")
    if fixture is not None:
        if isinstance(fixture, list):
            return [item for item in fixture if isinstance(item, dict)]
        if isinstance(fixture, dict):
            for key in ("items", "reminders", "data"):
                value = fixture.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    payload = run_json_command(["remindctl", "today", "--json"], cwd=root)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "reminders", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def load_memory_matches(root: Path, query: str, limit: int = 3) -> list[str]:
    memory_script = Path(__file__).resolve().parent / "assistant_memory.py"
    memory_path = root / "memory" / "assistant_memory.jsonl"
    payload = run_json_command(
        [
            "python3",
            str(memory_script),
            "--path",
            str(memory_path),
            "recall",
            "--query",
            query,
            "--limit",
            str(limit),
            "--json",
        ],
        cwd=root,
    )
    if not isinstance(payload, dict):
        return []
    matches = payload.get("matches")
    if not isinstance(matches, list):
        return []
    out: list[str] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            out.append(text)
    return out


def short_calendar_lines(calendar_payload: dict[str, Any], *, limit: int = 4) -> list[str]:
    events = calendar_payload.get("events")
    if not isinstance(events, list):
        return []
    lines: list[str] = []
    for event in events[:limit]:
        if not isinstance(event, dict):
            continue
        title = str(event.get("title", "")).strip() or "Untitled"
        start = str(event.get("startLocalTime", "")).strip()
        calendar = str(event.get("calendar", "")).strip()
        if start:
            lines.append(f"{start}: {title}" + (f" ({calendar})" if calendar else ""))
        else:
            lines.append(title + (f" ({calendar})" if calendar else ""))
    return lines


def short_reminder_lines(reminders: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    lines: list[str] = []
    for item in reminders[:limit]:
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue
        due = str(item.get("due") or item.get("dueDate") or item.get("when") or "").strip()
        list_name = str(item.get("list") or item.get("listName") or "").strip()
        prefix = f"{due}: " if due else ""
        suffix = f" ({list_name})" if list_name else ""
        lines.append(f"{prefix}{title}{suffix}")
    return lines
