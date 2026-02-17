#!/usr/bin/env python3
"""
Shared state helpers for inbox runner / notifier.

Design goals:
- tiny, dependency-free
- atomic writes (tmp + rename)
- tolerant parsing (corrupt state should not break workflows)
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ALLOWED_NOTIFY_CHANNELS = {"telegram", "discord", "none"}


def parse_notify_channels(raw: str) -> set[str]:
    """
    Parse Notify field values.

    Supported:
    - "telegram"
    - "discord"
    - "telegram,discord" (comma/space/plus separated)
    - "none" / empty -> no channels
    """
    s = (raw or "").strip().lower()
    if not s or s == "none":
        return set()
    parts = [p.strip() for p in re.split(r"[,+\s]+", s) if p.strip()]
    return {p for p in parts if p in ALLOWED_NOTIFY_CHANNELS and p != "none"}


def sha256_lines(lines: list[str]) -> str:
    h = hashlib.sha256()
    for ln in lines:
        h.update(str(ln).encode("utf-8", errors="replace"))
        h.update(b"\n")
    return h.hexdigest()


def load_kv_state(path: Path) -> dict[str, float]:
    """
    Load a dict[str,float] state file.

    Corrupt/invalid state returns {}.
    """
    try:
        if not path.exists():
            return {}
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in obj.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                out[k] = float(v)
        return out
    except Exception:
        return {}


def save_kv_state(path: Path, state: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)

