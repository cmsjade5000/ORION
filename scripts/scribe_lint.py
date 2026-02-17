#!/usr/bin/env python3
"""
Lint SCRIBE drafts against core output-contract rules.

Primary intent:
- prevent contract drift (header formats, emoji ban)
- enforce evidence-lock heuristics for news/update style drafts
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ALLOWED_HEADERS = {"TELEGRAM_MESSAGE:", "SLACK_MESSAGE:", "EMAIL_SUBJECT:", "INTERNAL:"}

# A pragmatic emoji detector (broad blocks + common emoji symbols). This is not perfect.
RE_EMOJI = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F1E6-\U0001F1FF]"
)

RE_URL = re.compile(r"https?://", flags=re.IGNORECASE)
RE_NEWSISH = re.compile(r"\b(latest|news|update|updates|breaking|announced|released|what changed)\b", flags=re.IGNORECASE)
RE_EVIDENCE_TAG = re.compile(r"\b(supported|inferred|needs-source)\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class LintError:
    line: int
    message: str


def _read_text(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def lint(text: str) -> list[LintError]:
    lines = (text or "").splitlines()
    errs: list[LintError] = []

    # Find first non-empty line.
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.strip():
            header_idx = i
            break
    if header_idx is None:
        return [LintError(1, "empty draft")]

    header = lines[header_idx].strip()
    if header not in ALLOWED_HEADERS:
        errs.append(
            LintError(
                header_idx + 1,
                f"first non-empty line must be one of {sorted(ALLOWED_HEADERS)!r} (got {header!r})",
            )
        )

    # Nothing may appear before the header besides blank lines.
    for j in range(0, header_idx):
        if lines[j].strip():
            errs.append(LintError(j + 1, "no text allowed before the header line"))
            break

    # Emoji ban.
    for i, ln in enumerate(lines, start=1):
        if RE_EMOJI.search(ln):
            errs.append(LintError(i, "emoji detected (SCRIBE outputs must not use emojis)"))
            break

    # Email contract: must include EMAIL_BODY after EMAIL_SUBJECT.
    if header == "EMAIL_SUBJECT:":
        has_body = any(ln.strip() == "EMAIL_BODY:" for ln in lines[header_idx + 1 :])
        if not has_body:
            errs.append(LintError(header_idx + 1, "EMAIL_SUBJECT requires an EMAIL_BODY: section"))

    # Evidence-lock heuristic: news/update drafts require at least one URL and at least one evidence tag.
    body = "\n".join(lines[header_idx + 1 :]).strip()
    if body and RE_NEWSISH.search(body):
        if not RE_URL.search(body):
            errs.append(LintError(header_idx + 1, "news/update style draft must include at least one URL"))
        if not RE_EVIDENCE_TAG.search(body):
            errs.append(
                LintError(
                    header_idx + 1,
                    "news/update style draft must include evidence tags: supported|inferred|needs-source",
                )
            )

    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Lint SCRIBE draft outputs.")
    ap.add_argument("--input", help="Draft file. If omitted, reads from stdin.")
    args = ap.parse_args()

    txt = _read_text(args.input)
    errs = lint(txt)
    if not errs:
        print("OK")
        return 0
    for e in errs:
        print(f"{e.line}: {e.message}", file=sys.stderr)
    print(f"FAIL: {len(errs)} issue(s)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

