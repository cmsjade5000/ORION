#!/usr/bin/env python3
"""
Shared routing-safety policy helpers for delegation packet delivery.
"""

from __future__ import annotations

try:
    from inbox_state import parse_notify_channels
except Exception:  # pragma: no cover
    from scripts.inbox_state import parse_notify_channels  # type: ignore


SPECIALIST_OWNERS = {
    "ATLAS",
    "POLARIS",
    "WIRE",
    "LEDGER",
    "EMBER",
    "NODE",
    "PULSE",
    "STRATUS",
    "PIXEL",
    "QUEST",
    "SCRIBE",
    "AEGIS",
}


def _normalize_owner(owner: str) -> str:
    return (owner or "").strip().upper()


def is_internal_specialist_owner(owner: str) -> bool:
    return _normalize_owner(owner) in SPECIALIST_OWNERS


def blocked_direct_telegram_delivery(owner: str, notify: str) -> bool:
    owner_norm = _normalize_owner(owner)
    if owner_norm not in SPECIALIST_OWNERS:
        return False

    notify_channels = parse_notify_channels(notify)
    return "telegram" in notify_channels
