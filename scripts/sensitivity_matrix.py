#!/usr/bin/env python3
"""
Minimal sensitivity / uncertainty helper for Decision Kernel outputs.

Input JSON schema (v1):
{
  "options": [
    {
      "name": "Option A",
      "scenarios": {
        "best":  120.0,
        "base":  80.0,
        "worst": 40.0
      }
    }
  ],
  "unit": "value points"  // optional
}

Interpretation:
- Higher scenario values are better.
- The script prints a compact best/base/worst table and the implied ranking.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Option:
    name: str
    best: float
    base: float
    worst: float


def _load_json(path: str | None) -> object:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _num(x: object, *, field: str) -> float:
    try:
        return float(x)  # type: ignore[arg-type]
    except Exception as e:
        raise ValueError(f"field {field!r} must be a number") from e


def parse_options(obj: dict) -> list[Option]:
    raw = obj.get("options")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing/empty 'options' list")
    out: list[Option] = []
    for i, it in enumerate(raw):
        if not isinstance(it, dict):
            raise ValueError(f"options[{i}] must be an object")
        name = str(it.get("name", "")).strip()
        if not name:
            raise ValueError(f"options[{i}].name is required")
        sc = it.get("scenarios")
        if not isinstance(sc, dict):
            raise ValueError(f"options[{i}].scenarios must be an object with best/base/worst")
        best = _num(sc.get("best"), field=f"options[{i}].scenarios.best")
        base = _num(sc.get("base"), field=f"options[{i}].scenarios.base")
        worst = _num(sc.get("worst"), field=f"options[{i}].scenarios.worst")
        out.append(Option(name=name, best=best, base=base, worst=worst))
    return out


def _fmt_table(opts: list[Option], unit: str) -> str:
    # Fixed-width table, ASCII only.
    name_w = max(6, max(len(o.name) for o in opts))
    def row(name: str, b: float, c: float, w: float) -> str:
        return f"{name:<{name_w}}  {b:>10.2f}  {c:>10.2f}  {w:>10.2f}"

    lines: list[str] = []
    lines.append(f"UNIT: {unit}")
    lines.append(f"{'option':<{name_w}}  {'best':>10}  {'base':>10}  {'worst':>10}")
    lines.append("-" * (name_w + 2 + 10 + 2 + 10 + 2 + 10))
    for o in opts:
        lines.append(row(o.name, o.best, o.base, o.worst))
    return "\n".join(lines)


def _rank(opts: list[Option], key: str) -> list[str]:
    return [o.name for o in sorted(opts, key=lambda x: getattr(x, key), reverse=True)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a best/base/worst sensitivity table for decision options.")
    ap.add_argument("--input", help="Path to JSON input. If omitted, reads from stdin.")
    args = ap.parse_args()

    obj = _load_json(args.input)
    if not isinstance(obj, dict):
        print("ERROR: input must be a JSON object", file=sys.stderr)
        return 2
    unit = str(obj.get("unit", "value")).strip() or "value"

    try:
        opts = parse_options(obj)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(_fmt_table(opts, unit))
    print("")
    print("RANKING:")
    print(f"- best:  {', '.join(_rank(opts, 'best'))}")
    print(f"- base:  {', '.join(_rank(opts, 'base'))}")
    print(f"- worst: {', '.join(_rank(opts, 'worst'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
