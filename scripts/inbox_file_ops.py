#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    from inbox_state import sha256_lines
except Exception:  # pragma: no cover
    from scripts.inbox_state import sha256_lines  # type: ignore


REQUIRED_PACKETS_HEADER = "## Packets"


@dataclasses.dataclass(frozen=True)
class PacketIdentity:
    idempotency_key: str
    content_hash: str


def packet_identity(*, fields: dict[str, str], packet_before_result: list[str]) -> PacketIdentity:
    return PacketIdentity(
        idempotency_key=(fields.get("Idempotency Key", "") or "").strip(),
        content_hash=sha256_lines(packet_before_result),
    )


@contextmanager
def locked_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        try:
            yield handle
        finally:
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(text)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def ensure_packets_header(lines: list[str], *, owner: str) -> list[str]:
    if any(line.strip() == REQUIRED_PACKETS_HEADER for line in lines):
        return lines
    if lines:
        return lines + ["", REQUIRED_PACKETS_HEADER]
    return [f"# {owner} Inbox", "", REQUIRED_PACKETS_HEADER]
