#!/usr/bin/env python3
"""Validate plan task dependency graphs in markdown files."""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from dataclasses import dataclass, field

RE_TASK_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+.*\b(T\d+)\b")
RE_DEPENDS = re.compile(r"^depends_on\s*:\s*(.+)\s*$", re.IGNORECASE)
RE_TASK_ID = re.compile(r"^T\d+$")


@dataclass
class TaskSection:
    task_id: str
    heading_line: int
    body: list[tuple[int, str]] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    depends_line: int | None = None


def _looks_like_plan(path: str) -> bool:
    name = os.path.basename(path).lower()
    if "plan" in name:
        return True

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                if RE_TASK_HEADING.match(raw.rstrip("\n")):
                    return True
    except OSError:
        return False

    return False


def discover_plan_files() -> list[str]:
    candidates = sorted(
        set(
            glob.glob(os.path.join("docs", "**", "*.md"), recursive=True)
            + glob.glob(os.path.join("tasks", "**", "*.md"), recursive=True)
        )
    )
    return [path for path in candidates if _looks_like_plan(path)]


def _strip_markdown_key_noise(line: str) -> str:
    text = line.strip()
    if text.startswith(("- ", "* ", "+ ")):
        text = text[2:].strip()
    return text.replace("**", "").replace("__", "").replace("`", "")


def _parse_depends_value(value: str) -> tuple[list[str] | None, str | None]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return None, "depends_on must use list syntax like [] or [T1, T2]"

    inner = value[1:-1].strip()
    if not inner:
        return [], None

    tokens = [token.strip() for token in inner.split(",")]
    if any(not token for token in tokens):
        return None, "depends_on list contains an empty entry"

    invalid = [token for token in tokens if not RE_TASK_ID.match(token)]
    if invalid:
        return None, f"depends_on entries must be task IDs like T1 (invalid: {', '.join(invalid)})"

    return tokens, None


def _extract_tasks(lines: list[str]) -> list[TaskSection]:
    tasks: list[TaskSection] = []
    current: TaskSection | None = None
    in_fence = False

    for line_no, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_fence = not in_fence

        heading_match = None if in_fence else RE_TASK_HEADING.match(line)
        if heading_match:
            if current is not None:
                tasks.append(current)
            current = TaskSection(task_id=heading_match.group(1), heading_line=line_no)
            continue

        if current is not None:
            current.body.append((line_no, line))

    if current is not None:
        tasks.append(current)

    return tasks


def _validate_depends(path: str, task: TaskSection) -> list[str]:
    errors: list[str] = []
    seen_depends = False

    for line_no, raw_line in task.body:
        normalized = _strip_markdown_key_noise(raw_line)
        match = RE_DEPENDS.match(normalized)
        if not match:
            continue

        if seen_depends:
            errors.append(f"{path}:{line_no}: task {task.task_id}: duplicate depends_on declaration")
            continue

        seen_depends = True
        deps, parse_error = _parse_depends_value(match.group(1))
        if parse_error:
            errors.append(f"{path}:{line_no}: task {task.task_id}: {parse_error}")
            continue

        task.depends_on = deps or []
        task.depends_line = line_no

    if not seen_depends:
        errors.append(
            f"{path}:{task.heading_line}: task {task.task_id}: missing required 'depends_on' declaration"
        )

    return errors


def _find_cycles(tasks: dict[str, TaskSection]) -> list[tuple[int, str]]:
    state: dict[str, int] = {}
    stack: list[str] = []
    stack_pos: dict[str, int] = {}
    cycles: list[tuple[int, str]] = []
    seen_signatures: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        state[node] = 1
        stack_pos[node] = len(stack)
        stack.append(node)

        for dep in tasks[node].depends_on:
            if dep not in tasks:
                continue
            dep_state = state.get(dep, 0)
            if dep_state == 0:
                dfs(dep)
            elif dep_state == 1:
                start_idx = stack_pos[dep]
                cycle = stack[start_idx:] + [dep]
                signature = tuple(cycle)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    line = tasks[node].depends_line or tasks[node].heading_line
                    cycles.append((line, f"cycle detected: {' -> '.join(cycle)}"))

        stack.pop()
        stack_pos.pop(node, None)
        state[node] = 2

    for task_id in tasks:
        if state.get(task_id, 0) == 0:
            dfs(task_id)

    return cycles


def validate_plan_file(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return [f"{path}:1: unable to read file ({exc})"]

    tasks = _extract_tasks(lines)
    if not tasks:
        return []

    errors: list[str] = []
    seen_ids: set[str] = set()
    by_id: dict[str, TaskSection] = {}

    for task in tasks:
        if task.task_id in seen_ids:
            errors.append(f"{path}:{task.heading_line}: duplicate task ID {task.task_id}")
            continue
        seen_ids.add(task.task_id)
        by_id[task.task_id] = task
        errors.extend(_validate_depends(path, task))

    for task in by_id.values():
        dep_line = task.depends_line or task.heading_line
        for dep in task.depends_on:
            if dep == task.task_id:
                errors.append(f"{path}:{dep_line}: task {task.task_id}: self-dependency is not allowed")
                continue
            if dep not in by_id:
                errors.append(f"{path}:{dep_line}: task {task.task_id}: unknown dependency '{dep}'")

    for line_no, message in _find_cycles(by_id):
        errors.append(f"{path}:{line_no}: {message}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate task dependency graphs in markdown plans.")
    parser.add_argument("paths", nargs="*", help="Plan markdown files to validate.")
    args = parser.parse_args()

    paths = args.paths or discover_plan_files()
    if not paths:
        print("OK: No plan files found.")
        return 0

    all_errors: list[str] = []
    for path in paths:
        all_errors.extend(validate_plan_file(path))

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        print(f"\nFAIL: {len(all_errors)} validation error(s).", file=sys.stderr)
        return 1

    print(f"OK: Validated {len(paths)} plan file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
