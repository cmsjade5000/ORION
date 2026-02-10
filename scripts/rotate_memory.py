#!/usr/bin/env python3
"""
Rotate memory: generate daily memory file from session dumps.

This script collects session dump files and compiles them into a daily memory
file located in the `memory/` directory with the naming convention YYYY-MM-DD.md.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
from pathlib import Path


def _iso_date(s: str) -> str:
    # Strict YYYY-MM-DD validation.
    try:
        return _dt.date.fromisoformat(s).isoformat()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid date (expected YYYY-MM-DD): {s}") from e


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rotate memory: compile session dumps into a daily memory file.")
    ap.add_argument("--repo-root", default=None, help="Override repo root (default: inferred from this script).")
    ap.add_argument("--date", type=_iso_date, default=_dt.date.today().isoformat(), help="Date for output file (YYYY-MM-DD).")
    ap.add_argument("--session-dir", default="memory/sessions", help="Relative session dump directory.")
    ap.add_argument("--output-dir", default="memory", help="Relative output directory.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite the daily file if it already exists.")
    ap.add_argument(
        "--prune-sessions",
        action="store_true",
        help="After writing, move session dumps into memory/sessions/archive/<date>/ (safe, reversible).",
    )
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else _default_repo_root()
    date = args.date

    memory_dir = (repo_root / args.output_dir).resolve()
    session_dir = (repo_root / args.session_dir).resolve()
    out_file = memory_dir / f"{date}.md"

    memory_dir.mkdir(parents=True, exist_ok=True)

    if out_file.exists() and not args.overwrite:
        print(f"Daily memory file already exists (use --overwrite): {out_file}")
        return 2

    session_files: list[Path] = []
    if session_dir.is_dir():
        session_files = sorted(session_dir.glob("*.md"))

    tmp_out = out_file.with_suffix(out_file.suffix + ".tmp")
    with tmp_out.open("w", encoding="utf-8", newline="\n") as out_f:
        out_f.write(f"# Memory for {date}\n\n")
        if session_files:
            out_f.write("## Session Dumps\n\n")
            for p in session_files:
                out_f.write(f"### {p.name}\n\n")
                try:
                    out_f.write(p.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    # Keep moving; don't hard-fail rotation on a single bad file.
                    out_f.write("*(Could not decode file as UTF-8.)*\n")
                out_f.write("\n\n")
        else:
            out_f.write("*(No session dumps found)*\n")

    os.replace(tmp_out, out_file)

    if args.prune_sessions and session_files:
        archive_dir = session_dir / "archive" / date
        archive_dir.mkdir(parents=True, exist_ok=True)
        for p in session_files:
            dest = archive_dir / p.name
            if dest.exists():
                # Avoid clobbering; keep the original session file in place.
                continue
            shutil.move(str(p), str(dest))

    print(f"MEMORY_ROTATED_OK date={date} out={out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
