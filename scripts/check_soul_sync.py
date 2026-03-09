#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_DIR = REPO_ROOT / "src" / "core" / "shared"
ROLES_DIR = REPO_ROOT / "src" / "agents"
AGENTS_DIR = REPO_ROOT / "agents"
USER_MD = REPO_ROOT / "USER.md"
SHARED_LAYERS = ["CONSTITUTION.md", "USER.md", "FOUNDATION.md", "ROUTING.md"]


def normalize_generated_line(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("**Generated:** "):
            lines[index] = "**Generated:** <normalized>"
    return "\n".join(lines).rstrip() + "\n"


def compose_expected(agent: str) -> str:
    parts: list[str] = [
        f"# SOUL.md — {agent}",
        "",
        "**Generated:** <normalized>",
        f"**Source:** src/core/shared + USER.md + src/agents/{agent}.md",
        "",
        "---",
        "",
    ]

    for name in SHARED_LAYERS:
        parts.append(f"<!-- BEGIN shared/{name} -->")
        if name == "USER.md":
            parts.append(USER_MD.read_text(encoding="utf-8").rstrip())
        else:
            parts.append((SHARED_DIR / name).read_text(encoding="utf-8").rstrip())
        parts.extend(
            [
                "",
                f"<!-- END shared/{name} -->",
                "",
                "---",
                "",
            ]
        )

    parts.extend(
        [
            f"<!-- BEGIN roles/{agent}.md -->",
            (ROLES_DIR / f"{agent}.md").read_text(encoding="utf-8").rstrip(),
            "",
            f"<!-- END roles/{agent}.md -->",
            "",
        ]
    )
    return "\n".join(parts)


def main() -> int:
    errors: list[str] = []

    for role_path in sorted(ROLES_DIR.glob("*.md")):
        agent = role_path.stem
        soul_path = AGENTS_DIR / agent / "SOUL.md"
        if not soul_path.exists():
            errors.append(f"missing generated artifact: {soul_path}")
            continue

        actual = normalize_generated_line(soul_path.read_text(encoding="utf-8"))
        expected = normalize_generated_line(compose_expected(agent))
        if actual != expected:
            errors.append(f"stale generated artifact: {soul_path}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print("Run `make soul` to regenerate SOUL artifacts.", file=sys.stderr)
        return 1

    print("SOUL artifacts are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
