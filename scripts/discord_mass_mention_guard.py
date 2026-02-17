#!/usr/bin/env python3
"""Guard outbound Discord text against mass mentions."""

from __future__ import annotations

import argparse
import re
import sys

# Match bare @everyone / @here while avoiding common false positives
# such as email-like strings and backslash-escaped tokens.
_MASS_MENTION_RE = re.compile(r"(?<![\\\w`])@(everyone|here)\b", re.IGNORECASE)


def find_mass_mentions(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _MASS_MENTION_RE.finditer(text):
        token = f"@{match.group(1).lower()}"
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def has_mass_mentions(text: str) -> bool:
    return bool(_MASS_MENTION_RE.search(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exit non-zero when Discord mass-mention tokens are present."
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to check. If omitted, reads from stdin.",
    )
    args = parser.parse_args(argv)

    text = args.text if args.text is not None else sys.stdin.read()
    hits = find_mass_mentions(text)
    if hits:
        sys.stderr.write(f"DISCORD_MASS_MENTION_BLOCKED: {', '.join(hits)}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
