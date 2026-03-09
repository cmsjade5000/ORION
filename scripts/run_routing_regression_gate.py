#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def build_commands(
    *,
    repo_root: Path,
    baseline: Path,
    latest_path: Path,
    compare_json: Path,
    compare_md: Path,
    thinking: str,
    timeout: int,
    tools_prompts_md: Path | None,
) -> list[list[str]]:
    eval_cmd = [
        sys.executable,
        str((repo_root / "scripts" / "loop_test_routing_sim.py").resolve()),
        "--repo-root",
        str(repo_root),
        "--thinking",
        thinking,
        "--timeout",
        str(timeout),
        "--out-dir",
        str((repo_root / "eval" / "history").resolve()),
        "--latest-path",
        str(latest_path),
    ]
    if tools_prompts_md is not None:
        eval_cmd.extend(["--tools-prompts-md", str(tools_prompts_md)])

    compare_cmd = [
        sys.executable,
        str((repo_root / "scripts" / "eval_compare.py").resolve()),
        "--baseline",
        str(baseline),
        "--current",
        str(latest_path),
        "--output-json",
        str(compare_json),
        "--output-md",
        str(compare_md),
    ]
    return [eval_cmd, compare_cmd]


def preflight(*, baseline: Path) -> list[str]:
    errors: list[str] = []
    if shutil.which("openclaw") is None:
        errors.append("missing required command: openclaw")
    if not baseline.exists():
        errors.append(f"missing baseline report: {baseline}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the opt-in live ORION routing regression lane."
    )
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--baseline", default="eval/history/baseline-2026-03.json")
    ap.add_argument("--latest-path", default="eval/latest_report.json")
    ap.add_argument("--output-json", default="eval/latest_compare.json")
    ap.add_argument("--output-md", default="eval/scorecard.md")
    ap.add_argument("--thinking", default="low")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--tools-prompts-md")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands and exit without running the live eval.",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    baseline = (repo_root / args.baseline).resolve() if not Path(args.baseline).is_absolute() else Path(args.baseline)
    latest_path = (repo_root / args.latest_path).resolve() if not Path(args.latest_path).is_absolute() else Path(args.latest_path)
    compare_json = (repo_root / args.output_json).resolve() if not Path(args.output_json).is_absolute() else Path(args.output_json)
    compare_md = (repo_root / args.output_md).resolve() if not Path(args.output_md).is_absolute() else Path(args.output_md)
    tools_prompts_md = None
    if args.tools_prompts_md:
        tools_prompts_md = (
            (repo_root / args.tools_prompts_md).resolve()
            if not Path(args.tools_prompts_md).is_absolute()
            else Path(args.tools_prompts_md)
        )

    errors = preflight(baseline=baseline)
    commands = build_commands(
        repo_root=repo_root,
        baseline=baseline,
        latest_path=latest_path,
        compare_json=compare_json,
        compare_md=compare_md,
        thinking=args.thinking,
        timeout=args.timeout,
        tools_prompts_md=tools_prompts_md,
    )

    if args.dry_run:
        print("ROUTING_REGRESSION_GATE")
        print(f"repo_root: {repo_root}")
        print(f"baseline: {baseline}")
        print(f"latest_path: {latest_path}")
        print(f"compare_json: {compare_json}")
        print(f"compare_md: {compare_md}")
        if tools_prompts_md is not None:
            print(f"tools_prompts_md: {tools_prompts_md}")
        if errors:
            for error in errors:
                print(f"preflight_error: {error}")
            return 2
        for index, command in enumerate(commands, start=1):
            print(f"cmd_{index}: {' '.join(command)}")
        return 0

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    env = dict(os.environ)
    for command in commands:
        subprocess.run(command, cwd=repo_root, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
