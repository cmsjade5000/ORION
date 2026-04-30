#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
import re

try:
    from inbox_state import sha256_lines
except Exception:  # pragma: no cover
    from scripts.inbox_state import sha256_lines  # type: ignore


REQUIRED_PACKETS_HEADER = "## Packets"
RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")


@dataclasses.dataclass(frozen=True)
class PacketIdentity:
    idempotency_key: str
    packet_id: str
    content_hash: str


def packet_identity(*, fields: dict[str, str], packet_before_result: list[str]) -> PacketIdentity:
    return PacketIdentity(
        idempotency_key=(fields.get("Idempotency Key", "") or "").strip(),
        packet_id=(fields.get("Packet ID", "") or "").strip(),
        content_hash=sha256_lines(packet_before_result),
    )


def strong_packet_identity(*, fields: dict[str, str], packet_before_result: list[str]) -> tuple[str, str]:
    identity = packet_identity(fields=fields, packet_before_result=packet_before_result)
    if identity.idempotency_key:
        return ("idempotency-key", identity.idempotency_key)
    if identity.packet_id:
        return ("packet-id", identity.packet_id)
    return ("content-hash", identity.content_hash)


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


def _split_packets(lines: list[str]) -> list[list[str]]:
    packets: list[list[str]] = []
    in_fence = False
    cur: list[str] | None = None
    for raw in lines:
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and RE_PACKET_HEADER.match(line):
            if cur is not None:
                packets.append(cur)
            cur = [line]
            continue
        if cur is not None:
            cur.append(line)
    if cur is not None:
        packets.append(cur)
    return packets


def _packet_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in packet_lines[1:]:
        match = RE_KV.match(line)
        if match:
            fields[match.group("key").strip()] = match.group("value").strip()
    return fields


def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in packet_lines:
        if line.strip() == "Result:":
            break
        out.append(line)
    return out


def append_packet_if_absent(
    path: Path,
    *,
    owner: str,
    packet_lines: list[str],
    source_markers: list[str] | None = None,
) -> bool:
    incoming_before = _packet_before_result(packet_lines)
    incoming_fields = _packet_fields(packet_lines)
    incoming = packet_identity(fields=incoming_fields, packet_before_result=incoming_before)
    markers = [marker for marker in (source_markers or []) if marker.strip()]
    lock_path = path.with_suffix(path.suffix + ".lock")

    with locked_file(lock_path):
        if path.exists():
            existing_lines = path.read_text(encoding="utf-8").splitlines()
        else:
            existing_lines = ensure_packets_header([], owner=owner)
        existing_lines = ensure_packets_header(existing_lines, owner=owner)
        existing_text = "\n".join(existing_lines).rstrip() + "\n"
        if any(marker in existing_text for marker in markers):
            return False

        for packet in _split_packets(existing_lines):
            existing = packet_identity(
                fields=_packet_fields(packet),
                packet_before_result=_packet_before_result(packet),
            )
            if incoming.idempotency_key and incoming.idempotency_key == existing.idempotency_key:
                return False
            if incoming.packet_id and incoming.packet_id == existing.packet_id:
                return False
            if incoming.content_hash == existing.content_hash:
                return False

        content = existing_text.rstrip() + "\n\n" + "\n".join(packet_lines).rstrip() + "\n"
        atomic_write_text(path, content)
    return True
