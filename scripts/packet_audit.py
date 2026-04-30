#!/usr/bin/env python3
"""Read-only global consistency audit for ORION Task Packets."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from inbox_file_ops import ParsedPacket, parse_inbox_packets, sha256_lines
import validate_task_packets as packet_validator


TERMINAL_STATUSES = {"OK", "FAILED", "BLOCKED", "CANCELLED"}


@dataclasses.dataclass(frozen=True)
class AuditIssue:
    code: str
    severity: str
    message: str
    path: str
    line: int
    detail: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "detail": self.detail,
        }


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _packet_job_id(packet: ParsedPacket) -> str:
    if packet.identity.idempotency_key:
        return "ik-" + sha256_lines([packet.identity.idempotency_key])[:16]
    return "pkt-" + packet.identity.content_hash[:16]


def _identity_entries(packet: ParsedPacket) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if packet.identity.idempotency_key:
        out.append(("idempotency-key", packet.identity.idempotency_key))
    if packet.identity.packet_id:
        out.append(("packet-id", packet.identity.packet_id))
    if packet.identity.content_hash:
        out.append(("content-hash", packet.identity.content_hash))
    return out


def _duplicate_severity(first: ParsedPacket, duplicate: ParsedPacket) -> str:
    if first.result_status in TERMINAL_STATUSES and duplicate.result_status in TERMINAL_STATUSES:
        return "warn"
    return "error"


def _location(packet: ParsedPacket) -> str:
    return f"{packet.display_path}:{packet.start_line}"


def _is_generated(packet: ParsedPacket) -> bool:
    idem = packet.identity.idempotency_key.lower()
    if idem.startswith(("recovery:", "handoff:")):
        return True
    return bool(packet.fields.get("Handoff Source", "").strip() or packet.fields.get("Recovery Source", "").strip())


def _is_recovery_or_triage(packet: ParsedPacket) -> bool:
    idem = packet.identity.idempotency_key.lower()
    objective = str(packet.fields.get("Objective", "")).lower()
    return idem.startswith("recovery:") or "recover stale" in objective or "triage" in objective


def _packet_sections(packet: ParsedPacket) -> dict[str, list[str]]:
    required = packet_validator.REQUIRED_SECTIONS
    sections: dict[str, list[str]] = {section: [] for section in required}
    current: str | None = None
    for line in packet.lines[1:]:
        match = packet_validator.RE_KV.match(line)
        if match:
            key = match.group("key").strip()
            value = match.group("value").strip()
            if key in sections:
                current = key
                if value:
                    sections[key].append(value)
            else:
                current = None
            continue
        if current:
            stripped = line.strip()
            if not stripped:
                continue
            sections[current].append(stripped[2:].strip() if stripped.startswith("- ") else stripped)
    return sections


def _route_issue(packet: ParsedPacket) -> AuditIssue | None:
    sections = _packet_sections(packet)
    inferred = packet_validator.infer_expected_owner(packet.fields, sections)
    owner = str(packet.fields.get("Owner", "")).strip().upper()
    contract_owners = getattr(packet_validator, "CONTRACT_OWNERS", set())
    has_override = packet_validator._has_routing_override(packet.fields)
    if inferred and inferred in contract_owners and owner and owner != inferred and not has_override:
        return AuditIssue(
            code="route_mismatch",
            severity="warn",
            message=f"routing decision expects Owner {inferred!r}, got {owner!r}",
            path=packet.display_path,
            line=packet.start_line,
            detail={"expected_owner": inferred, "owner": owner},
        )
    return None


def load_packets(repo_root: Path) -> list[ParsedPacket]:
    inbox_dir = repo_root / "tasks" / "INBOX"
    if not inbox_dir.exists():
        return []
    packets: list[ParsedPacket] = []
    for path in sorted(inbox_dir.glob("*.md")):
        packets.extend(parse_inbox_packets(path, repo_root=repo_root))
    return packets


def audit_packets(repo_root: Path) -> dict[str, object]:
    packets = load_packets(repo_root)
    issues: list[AuditIssue] = []

    identity_seen: dict[tuple[str, str], ParsedPacket] = {}
    packet_by_id: dict[str, ParsedPacket] = {}
    terminal_by_id: dict[str, ParsedPacket] = {}
    terminal_roots: set[str] = set()

    for packet in packets:
        packet_id = packet.fields.get("Packet ID", "").strip()
        if packet_id:
            packet_by_id[packet_id] = packet
            if packet.result_status in TERMINAL_STATUSES:
                terminal_by_id[packet_id] = packet
        root = packet.fields.get("Root Packet ID", "").strip()
        if packet.result_status in TERMINAL_STATUSES and root:
            terminal_roots.add(root)
        for identity in _identity_entries(packet):
            first = identity_seen.get(identity)
            if first is None:
                identity_seen[identity] = packet
                continue
            severity = _duplicate_severity(first, packet)
            issues.append(
                AuditIssue(
                    code="duplicate_identity",
                    severity=severity,
                    message=f"duplicate {identity[0]} appears in multiple packets",
                    path=packet.display_path,
                    line=packet.start_line,
                    detail={
                        "identity_type": identity[0],
                        "identity_value": identity[1],
                        "first": _location(first),
                        "duplicate": _location(packet),
                    },
                )
            )

    for packet in packets:
        if _is_generated(packet):
            missing = [
                field
                for field in ("Parent Packet ID", "Root Packet ID", "Workflow ID")
                if not packet.fields.get(field, "").strip()
            ]
            if missing:
                issues.append(
                    AuditIssue(
                        code="missing_generated_lineage",
                        severity="warn",
                        message="generated packet is missing lineage fields",
                        path=packet.display_path,
                        line=packet.start_line,
                        detail={"missing": missing},
                    )
                )

        parent = packet.fields.get("Parent Packet ID", "").strip()
        if parent and parent not in packet_by_id:
            issues.append(
                AuditIssue(
                    code="dangling_parent",
                    severity="error",
                    message="Parent Packet ID does not point to a visible packet",
                    path=packet.display_path,
                    line=packet.start_line,
                    detail={"parent_packet_id": parent},
                )
            )

        if packet.result_status is None and _is_recovery_or_triage(packet):
            parent_terminal = terminal_by_id.get(parent) if parent else None
            root = packet.fields.get("Root Packet ID", "").strip()
            root_terminal = bool(root and root in terminal_roots)
            if parent_terminal is not None or root_terminal:
                issues.append(
                    AuditIssue(
                        code="terminal_source_active_descendant",
                        severity="error",
                        message="pending recovery/triage packet has terminal source lineage",
                        path=packet.display_path,
                        line=packet.start_line,
                        detail={"parent_packet_id": parent, "root_packet_id": root},
                    )
                )

        route_issue = _route_issue(packet)
        if route_issue is not None:
            issues.append(route_issue)

    summary = _load_json(repo_root / "tasks" / "JOBS" / "summary.json", {})
    summary_jobs = summary.get("jobs", []) if isinstance(summary, dict) else []
    summary_job_ids = {
        str(job.get("job_id") or "")
        for job in summary_jobs
        if isinstance(job, dict)
    }
    if summary_job_ids:
        for packet in packets:
            job_id = _packet_job_id(packet)
            if job_id not in summary_job_ids:
                issues.append(
                    AuditIssue(
                        code="summary_missing_packet",
                        severity="warn",
                        message="visible inbox packet has no matching job summary record",
                        path=packet.display_path,
                        line=packet.start_line,
                        detail={"job_id": job_id},
                    )
                )

    issue_dicts = [issue.to_dict() for issue in issues]
    counts: dict[str, int] = {"packets": len(packets), "error": 0, "warn": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return {
        "ok": counts.get("error", 0) == 0,
        "issue_count": len(issues),
        "counts": counts,
        "issues": issue_dicts,
    }


def _render_text(report: dict[str, object]) -> str:
    counts = report.get("counts", {}) if isinstance(report.get("counts"), dict) else {}
    lines = [
        f"PACKET_AUDIT {'OK' if report.get('ok') else 'WARN'}",
        f"packets: {counts.get('packets', 0)}",
        f"issues: {report.get('issue_count', 0)}",
        f"errors: {counts.get('error', 0)} warnings: {counts.get('warn', 0)}",
    ]
    for issue in report.get("issues", []) if isinstance(report.get("issues"), list) else []:
        if not isinstance(issue, dict):
            continue
        lines.append(
            f"- {issue.get('severity')} {issue.get('code')} {issue.get('path')}:{issue.get('line')} {issue.get('message')}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit global ORION Task Packet consistency.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on warnings as well as errors.")
    args = parser.parse_args(argv)

    report = audit_packets(Path(args.repo_root).resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_render_text(report))

    counts = report.get("counts", {}) if isinstance(report.get("counts"), dict) else {}
    if int(counts.get("error", 0) or 0) > 0:
        return 1
    if args.strict and int(report.get("issue_count", 0) or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
