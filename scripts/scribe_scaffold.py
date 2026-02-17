#!/usr/bin/env python3
"""
Deterministic scaffold generator for SCRIBE-style drafts.

This does NOT attempt to write the final message content; it produces a contract-compliant
starting structure with placeholders and (optional) evidence items.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: str | None) -> object:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _as_list(obj: dict[str, Any], key: str) -> list[str]:
    v = obj.get(key, [])
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for it in v:
        s = str(it).strip()
        if s:
            out.append(s)
    return out


def _evidence_lines(obj: dict[str, Any]) -> list[str]:
    items = obj.get("evidence_items", [])
    if not isinstance(items, list) or not items:
        return []
    out: list[str] = []
    for it in items[:6]:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip() or "(untitled)"
        url = str(it.get("url", "")).strip()
        tag = str(it.get("tag", "supported")).strip().lower()
        if tag not in {"supported", "inferred", "needs-source"}:
            tag = "supported"
        if url:
            out.append(f"- {title} ({tag}): {url}")
        else:
            out.append(f"- {title} ({tag}): (missing url)")
    return out


def scaffold(destination: str, payload: dict[str, Any]) -> str:
    dest = (destination or "").strip().lower()
    if dest not in {"telegram", "slack", "email", "internal"}:
        raise ValueError("destination must be one of: telegram|slack|email|internal")

    goal = str(payload.get("goal", "")).strip() or "(goal missing)"
    tone = str(payload.get("tone", "calm, pragmatic")).strip()
    must = _as_list(payload, "must_include")
    must_not = _as_list(payload, "must_not_include")
    ev = _evidence_lines(payload)

    if dest == "telegram":
        lines = ["TELEGRAM_MESSAGE:"]
        lines.append(f"[{tone}] {goal}")
        if must:
            lines.append("Must include:")
            lines.extend([f"- {x}" for x in must[:6]])
        if ev:
            lines.append("Evidence:")
            lines.extend(ev)
        if must_not:
            lines.append("Must not include:")
            lines.extend([f"- {x}" for x in must_not[:6]])
        lines.append("")
        lines.append("Draft:")
        lines.append("- (write 1-8 sentences here; include URLs + evidence tags when making time-sensitive claims)")
        return "\n".join(lines).rstrip() + "\n"

    if dest == "slack":
        lines = ["SLACK_MESSAGE:"]
        lines.append(f"[{tone}] {goal}")
        if must:
            lines.append("Must include:")
            lines.extend([f"- {x}" for x in must[:8]])
        if ev:
            lines.append("Evidence:")
            lines.extend(ev)
        if must_not:
            lines.append("Must not include:")
            lines.extend([f"- {x}" for x in must_not[:8]])
        lines.append("")
        lines.append("Draft:")
        lines.append("- (write short paragraphs and bullets here)")
        return "\n".join(lines).rstrip() + "\n"

    if dest == "email":
        subj = str(payload.get("email_subject", "")).strip() or "(subject placeholder)"
        lines = ["EMAIL_SUBJECT:", subj, "EMAIL_BODY:"]
        lines.append(f"[{tone}] {goal}")
        if must:
            lines.append("")
            lines.append("Must include:")
            lines.extend([f"- {x}" for x in must[:10]])
        if ev:
            lines.append("")
            lines.append("Evidence:")
            lines.extend(ev)
        if must_not:
            lines.append("")
            lines.append("Must not include:")
            lines.extend([f"- {x}" for x in must_not[:10]])
        lines.append("")
        lines.append("(Draft body here; keep it plain text and scannable.)")
        return "\n".join(lines).rstrip() + "\n"

    # internal
    lines = ["INTERNAL:"]
    lines.append(f"Goal: {goal}")
    lines.append(f"Tone: {tone}")
    if must:
        lines.append("Must include:")
        lines.extend([f"- {x}" for x in must[:10]])
    if ev:
        lines.append("Evidence:")
        lines.extend(ev)
    if must_not:
        lines.append("Must not include:")
        lines.extend([f"- {x}" for x in must_not[:10]])
    lines.append("Notes:")
    lines.append("- (add structured bullets here)")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a SCRIBE contract-compliant scaffold.")
    ap.add_argument("--destination", required=True, help="telegram|slack|email|internal")
    ap.add_argument("--input", help="JSON input file. If omitted, reads JSON from stdin.")
    args = ap.parse_args()

    try:
        obj = _read_json(args.input)
    except Exception as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(obj, dict):
        print("ERROR: input must be a JSON object", file=sys.stderr)
        return 2

    try:
        out = scaffold(args.destination, obj)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

