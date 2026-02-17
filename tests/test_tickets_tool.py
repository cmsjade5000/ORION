from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=str(cwd), check=True, text=True, capture_output=True)
    return p.stdout.strip()


def test_tickets_next_and_new(tmp_path: Path) -> None:
    # Create a minimal tasks/ structure in a temp dir.
    tasks = tmp_path / "tasks"
    (tasks / "WORK" / "backlog").mkdir(parents=True)
    (tasks / "WORK" / "artifacts").mkdir(parents=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "tickets.py"

    assert run(["python3", str(script), "--tasks-dir", str(tasks), "next"], cwd=tmp_path) == "0001"

    ticket_path = run(
        [
            "python3",
            str(script),
            "--tasks-dir",
            str(tasks),
            "new",
            "--title",
            "Example Ticket",
        ],
        cwd=tmp_path,
    )
    p = Path(ticket_path)
    assert p.exists()
    assert p.name.startswith("0001-")

    # Next number should advance.
    assert run(["python3", str(script), "--tasks-dir", str(tasks), "next"], cwd=tmp_path) == "0002"


def test_tickets_move_updates_status(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    (tasks / "WORK" / "backlog").mkdir(parents=True)
    (tasks / "WORK" / "in-progress").mkdir(parents=True)
    (tasks / "WORK" / "artifacts").mkdir(parents=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "tickets.py"

    ticket_path = run(
        ["python3", str(script), "--tasks-dir", str(tasks), "new", "--title", "Move Me"],
        cwd=tmp_path,
    )
    p = Path(ticket_path)
    assert p.exists()

    moved_path = run(
        [
            "python3",
            str(script),
            "--tasks-dir",
            str(tasks),
            "move",
            "--ticket",
            "1",
            "--to",
            "in-progress",
            "--note",
            "started work",
        ],
        cwd=tmp_path,
    )
    mp = Path(moved_path)
    assert mp.exists()
    assert mp.parent.name == "in-progress"

    md = mp.read_text(encoding="utf-8")
    assert "Status: in-progress" in md
    assert "started work" in md
