#!/usr/bin/env python3
"""
Minimal, repo-native ticket helper for the file-first workflow in tasks/.

Design goals:
- No external dependencies.
- Safe by default (create-only).
- Testable (paths can be overridden).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
from pathlib import Path


TICKET_RE = re.compile(r"^(?P<num>\d{4})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")

LANES = ("backlog", "in-progress", "testing", "done")

LANE_TO_STATUS = {
    "backlog": "queued",
    "in-progress": "in-progress",
    "testing": "testing",
    "done": "done",
}


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    return s or "ticket"


def iter_ticket_numbers(tasks_dir: Path) -> list[int]:
    nums: list[int] = []
    for lane in ("backlog", "in-progress", "testing", "done"):
        d = tasks_dir / "WORK" / lane
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            m = TICKET_RE.match(p.name)
            if not m:
                continue
            nums.append(int(m.group("num")))
    return nums


def next_ticket_number(tasks_dir: Path) -> int:
    nums = iter_ticket_numbers(tasks_dir)
    return (max(nums) + 1) if nums else 1


def ticket_filename(num: int, slug: str) -> str:
    return f"{num:04d}-{slug}.md"


def build_ticket_md(num: int, title: str, owner: str, status: str, intake: str | None) -> str:
    header_title = f"{num:04d}-{slugify(title)}"
    lines: list[str] = []
    lines.append(f"# {header_title}")
    lines.append("")
    lines.append(f"Owner: {owner}")
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("## Context")
    if intake:
        lines.append(f"- Intake: {intake}")
    else:
        lines.append("- (why this exists)")
    lines.append("")
    lines.append("## Requirements")
    lines.append("- (fill)")
    lines.append("")
    lines.append("## Acceptance Criteria")
    lines.append("- (fill)")
    lines.append("")
    lines.append("## Artifacts")
    lines.append(f"- tasks/WORK/artifacts/{header_title}/")
    lines.append("")
    lines.append("## Notes")
    lines.append(f"- {dt.datetime.now().strftime('%Y-%m-%d')}: ticket created")
    lines.append("")
    return "\n".join(lines)


def parse_ticket_selector(s: str) -> tuple[str, str]:
    """
    Returns (kind, value):
    - ("path", <path>) when s looks like a path that exists
    - ("num", <4-digit>) when s is 1-4 digits
    - ("name", <raw>) otherwise
    """
    p = Path(s)
    if p.exists():
        return ("path", str(p))
    if re.fullmatch(r"\d{1,4}", s.strip()):
        return ("num", f"{int(s):04d}")
    return ("name", s.strip())


def find_ticket_file(tasks_dir: Path, selector: str) -> Path:
    kind, value = parse_ticket_selector(selector)
    if kind == "path":
        p = Path(value).resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        return p

    matches: list[Path] = []
    for lane in LANES:
        lane_dir = tasks_dir / "WORK" / lane
        if not lane_dir.exists():
            continue
        if kind == "num":
            matches.extend(sorted(lane_dir.glob(f"{value}-*.md")))
        else:
            needle = value.lower()
            for p in lane_dir.glob("*.md"):
                if p.name.lower() == needle or needle in p.name.lower():
                    matches.append(p)

    uniq = sorted({p.resolve() for p in matches})
    if not uniq:
        raise FileNotFoundError(f"Ticket not found in lanes: {selector}")
    if len(uniq) > 1:
        rendered = "\n".join(f"- {p}" for p in uniq[:10])
        more = "" if len(uniq) <= 10 else f"\n- ... ({len(uniq) - 10} more)"
        raise SystemExit(f"Ambiguous selector: {selector}\nMatches:\n{rendered}{more}")
    return uniq[0]


def rewrite_status(md: str, new_status: str) -> str:
    # Normalize: remove any existing Status: lines, then insert one canonical line.
    # This makes the operation idempotent even if a file got duplicate status lines.
    lines = md.splitlines()
    kept: list[str] = [ln for ln in lines if not ln.startswith("Status:")]

    # Collapse extra blank lines in the preamble (before the first section header).
    pre_end = len(kept)
    for i, ln in enumerate(kept):
        if ln.startswith("## "):
            pre_end = i
            break
    pre = kept[:pre_end]
    rest = kept[pre_end:]
    collapsed: list[str] = []
    last_blank = False
    for ln in pre:
        is_blank = (ln.strip() == "")
        if is_blank and last_blank:
            continue
        collapsed.append(ln)
        last_blank = is_blank
    kept = collapsed + rest

    insert_line = f"Status: {new_status}"

    # Prefer inserting immediately after Owner: if present.
    for i, ln in enumerate(kept):
        if ln.startswith("Owner:"):
            kept.insert(i + 1, insert_line)
            return "\n".join(kept).rstrip() + "\n"

    # Else insert after the first H1.
    for i, ln in enumerate(kept):
        if ln.startswith("# "):
            # Put a blank line between header and metadata if needed.
            kept.insert(i + 1, "")
            kept.insert(i + 2, insert_line)
            return "\n".join(kept).rstrip() + "\n"

    # Fallback: prepend.
    return (insert_line + "\n\n" + "\n".join(kept)).rstrip() + "\n"


def append_note(md: str, note: str) -> str:
    if "## Notes" in md:
        head, tail = md.split("## Notes", 1)
        tail = tail.lstrip("\n")
        return f"{head}## Notes\n- {note}\n{tail}"
    return md.rstrip() + f"\n\n## Notes\n- {note}\n"


def cmd_next(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir).resolve()
    print(f"{next_ticket_number(tasks_dir):04d}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir).resolve()
    title = args.title.strip()
    slug = slugify(args.slug or title)
    num = next_ticket_number(tasks_dir)

    lane_dir = tasks_dir / "WORK" / args.lane
    lane_dir.mkdir(parents=True, exist_ok=True)

    filename = ticket_filename(num, slug)
    ticket_path = lane_dir / filename

    if ticket_path.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite existing ticket: {ticket_path} (pass --overwrite)")

    intake_ref = args.intake
    md = build_ticket_md(num=num, title=title, owner=args.owner, status=args.status, intake=intake_ref)
    ticket_path.write_text(md, encoding="utf-8")

    # Seed artifact directory for convenience.
    artifacts_dir = tasks_dir / "WORK" / "artifacts" / f"{num:04d}-{slugify(title)}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    print(str(ticket_path))
    return 0


def cmd_move(args: argparse.Namespace) -> int:
    tasks_dir = Path(args.tasks_dir).resolve()
    to_lane = args.to

    src = find_ticket_file(tasks_dir, args.ticket)
    dest_dir = tasks_dir / "WORK" / to_lane
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    new_status = args.status or LANE_TO_STATUS[to_lane]

    md = src.read_text(encoding="utf-8")
    md2 = rewrite_status(md, new_status)
    if args.note:
        today = dt.datetime.now().strftime("%Y-%m-%d")
        md2 = append_note(md2, f"{today}: {args.note}")

    if src.resolve() == dest.resolve():
        if md2 != md:
            src.write_text(md2, encoding="utf-8")
        print(str(dest))
        return 0

    if dest.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite destination: {dest} (pass --overwrite)")

    if md2 != md:
        src.write_text(md2, encoding="utf-8")

    if dest.exists() and args.overwrite:
        dest.unlink()
    src.rename(dest)

    print(str(dest))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tickets.py", description="Repo-native ticket helper (tasks/WORK lanes).")
    p.add_argument(
        "--tasks-dir",
        default=os.environ.get("ORION_TASKS_DIR", "tasks"),
        help="Path to tasks/ (default: tasks or $ORION_TASKS_DIR).",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("next", help="Print the next available ticket number.")
    sp.set_defaults(func=cmd_next)

    sp = sub.add_parser("new", help="Create a new ticket in a lane (default: backlog).")
    sp.add_argument("--title", required=True, help="Short human title.")
    sp.add_argument("--slug", help="Override slug (kebab-case will be enforced).")
    sp.add_argument("--owner", default="ORION", help="Owner field value (default: ORION).")
    sp.add_argument("--status", default="queued", help="Status field value (default: queued).")
    sp.add_argument(
        "--lane",
        default="backlog",
        choices=["backlog", "in-progress", "testing", "done"],
        help="Which lane to create the ticket in (default: backlog).",
    )
    sp.add_argument("--intake", help="Optional intake reference path (e.g. tasks/INTAKE/2026-02-17-foo.md).")
    sp.add_argument("--overwrite", action="store_true", help="Overwrite if the target ticket file exists.")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("move", help="Move a ticket between lanes and rewrite Status: to match.")
    sp.add_argument("--ticket", required=True, help="Selector: number (e.g. 12), filename/substring, or path.")
    sp.add_argument("--to", required=True, choices=list(LANES), help="Destination lane.")
    sp.add_argument("--status", help="Override Status: value (default is lane-derived).")
    sp.add_argument("--note", help="Optional note to append under ## Notes (dated).")
    sp.add_argument("--overwrite", action="store_true", help="Overwrite destination if it exists.")
    sp.set_defaults(func=cmd_move)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
