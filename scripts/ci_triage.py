#!/usr/bin/env python3
"""
Lightweight GitHub Actions CI triage helper (STRATUS-oriented).

This script is intentionally conservative:
- no mutations (read-only gh queries)
- outputs a short, copy/paste-friendly summary

It is safe to use as an input to Task Packet Result blocks.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Triage:
    category: str
    signals: list[str]
    next_steps: list[str]


def classify_failed_log(txt: str) -> Triage:
    s = txt or ""
    low = s.lower()

    signals: list[str] = []
    next_steps: list[str] = []

    def sig(pat: str) -> bool:
        m = re.search(pat, s, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            signals.append(m.group(0).strip()[:160])
            return True
        return False

    # Common buckets (order matters).
    if sig(r"\bno module named\b") or sig(r"\bmodule not found\b") or sig(r"\bcannot find module\b"):
        category = "deps/import"
        next_steps = [
            "Check lockfiles / dependency install step.",
            "Confirm the test runner matches the repo standard (npm test / unittest).",
        ]
        return Triage(category, signals, next_steps)

    if "pytest" in low and ("no module named pytest" in low or "command not found: pytest" in low):
        category = "test-runner-mismatch"
        next_steps = [
            "Prefer repo default runner (npm test) instead of pytest unless explicitly installed.",
            "Convert pytest-only tests to unittest or gate them behind availability.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\bassertionerror\b") or sig(r"\bfail(?:ed)?\b") or "ran " in low and "failed" in low:
        category = "tests"
        next_steps = [
            "Re-run locally: npm test (or the failing step command).",
            "Inspect the first failing test and recent diffs.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\btsc\b.*\berror\b") or sig(r"\btypescript\b.*\berror\b"):
        category = "typecheck"
        next_steps = [
            "Re-run the typecheck step locally.",
            "Fix the first reported type error; cascading errors often disappear after.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\bnpm\b.*\bERR!\b") or sig(r"\byarn\b.*\berror\b") or sig(r"\bpnpm\b.*\berror\b"):
        category = "node-build"
        next_steps = [
            "Inspect install/build logs for the first error line above.",
            "Verify Node version and lockfile consistency.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\bpermission denied\b") or sig(r"\bauthorization\b") or sig(r"\bdenied\b"):
        category = "auth/permissions"
        next_steps = [
            "Check token/permissions used by the workflow and repo secrets configuration.",
            "Confirm the job has required permissions in workflow YAML.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\btimeout\b") or sig(r"\bETIMEDOUT\b") or sig(r"\bECONNRESET\b"):
        category = "network/timeout"
        next_steps = [
            "Check for flaky network calls; add retries/backoff where safe.",
            "Consider marking the step as retryable if supported.",
        ]
        return Triage(category, signals, next_steps)

    if sig(r"\bOOM\b") or sig(r"\bout of memory\b") or sig(r"\bkilled\b"):
        category = "resources"
        next_steps = [
            "Reduce parallelism, memory usage, or split the job.",
            "Check runner size / limits for the workflow.",
        ]
        return Triage(category, signals, next_steps)

    category = "unknown"
    next_steps = [
        "Scan the failed-step logs for the first error line and missing prerequisites.",
        "If logs are too long, re-run locally or narrow to failing step only.",
    ]
    # Keep at least one short signal for UX.
    if not signals:
        m = re.search(r"(?im)^.*(error|failed|exception).*$", s)
        if m:
            signals.append(m.group(0).strip()[:160])
    return Triage(category, signals, next_steps)


def _gh(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Triage a GitHub Actions run by id/url (read-only).")
    ap.add_argument("run", help="Run id or run URL")
    ap.add_argument("--repo", default=None, help="Explicit repo (owner/repo). Optional when run is URL or in repo.")
    args = ap.parse_args()

    base: list[str] = ["run", "view", args.run, "--log-failed"]
    if args.repo:
        base += ["--repo", args.repo]

    r = _gh(*base)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        print(f"ERROR: gh run view failed: {msg}", file=sys.stderr)
        return 2

    tri = classify_failed_log(r.stdout)
    print(f"CATEGORY: {tri.category}")
    if tri.signals:
        print("SIGNALS:")
        for ln in tri.signals[:6]:
            print(f"- {ln}")
    print("NEXT:")
    for ln in tri.next_steps:
        print(f"- {ln}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

