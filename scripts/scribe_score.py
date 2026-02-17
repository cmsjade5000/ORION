#!/usr/bin/env python3
"""
Quality scorer for SCRIBE drafts.

This is not a linter (scribe_lint.py is). This provides a quick scorecard
to help ORION decide whether a draft needs another pass.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from scribe_lint import lint
except Exception:  # pragma: no cover
    from scripts.scribe_lint import lint  # type: ignore


RE_URL = re.compile(r"https?://", flags=re.IGNORECASE)


@dataclass(frozen=True)
class Score:
    compliance: int
    clarity: int
    evidence: int
    notes: list[str]

    @property
    def total(self) -> int:
        return self.compliance + self.clarity + self.evidence


def _read_text(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def score(text: str) -> Score:
    notes: list[str] = []

    errs = lint(text)
    compliance = 40 if not errs else max(0, 40 - (10 * min(4, len(errs))))
    if errs:
        notes.append(f"lint issues: {len(errs)} (run scripts/scribe_lint.py for details)")

    lines = (text or "").splitlines()
    body = "\n".join(lines[1:]).strip() if lines else ""

    # Clarity heuristic (40 points).
    clarity = 40
    if len(body) < 10:
        clarity -= 10
        notes.append("very short body; may be incomplete")
    if len(body) > 2500:
        clarity -= 10
        notes.append("long body; may be too verbose for the destination")
    if body.count("\n\n") == 0 and len(body) > 500:
        clarity -= 5
        notes.append("no paragraph breaks; consider adding structure")

    # Evidence heuristic (20 points).
    evidence = 20
    if "latest" in body.lower() or "update" in body.lower() or "news" in body.lower():
        if not RE_URL.search(body):
            evidence -= 10
            notes.append("news/update phrasing but no URL found")
    if not RE_URL.search(body):
        evidence -= 5
        notes.append("no URL present (ok for many drafts, but check if time-sensitive)")

    compliance = max(0, min(40, compliance))
    clarity = max(0, min(40, clarity))
    evidence = max(0, min(20, evidence))
    return Score(compliance=compliance, clarity=clarity, evidence=evidence, notes=notes)


def main() -> int:
    ap = argparse.ArgumentParser(description="Score a SCRIBE draft for quick triage.")
    ap.add_argument("--input", help="Draft file. If omitted, reads from stdin.")
    args = ap.parse_args()

    txt = _read_text(args.input)
    sc = score(txt)
    print(f"SCORE: {sc.total}/100")
    print(f"- compliance: {sc.compliance}/40")
    print(f"- clarity: {sc.clarity}/40")
    print(f"- evidence: {sc.evidence}/20")
    if sc.notes:
        print("NOTES:")
        for n in sc.notes:
            print(f"- {n}")
    return 0 if sc.total >= 70 else 1


if __name__ == "__main__":
    raise SystemExit(main())
