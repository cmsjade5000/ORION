#!/usr/bin/env python3
"""
Weekly Task Packet routing audit.

Outputs concise ORION-facing counts for:
- misroutes/requester policy violations
- Kalshi policy/risk gate misses
- notification noise (Notify set without Result)
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
from dataclasses import dataclass

import validate_task_packets as v


MISROUTE_MARKERS = (
    "Owner looks like a placeholder",
    "does not match inbox",
    "Requester must be one of",
)


@dataclass
class AuditTotals:
    inbox_files: int = 0
    packets_scanned: int = 0
    misroutes_or_requester_violations: int = 0
    kalshi_gate_misses: int = 0
    notification_noise: int = 0
    polaris_active: int = 0
    polaris_oldest_days: int = 0
    polaris_aging_gt_24h: int = 0
    polaris_aging_gt_48h: int = 0
    polaris_aging_gt_72h: int = 0
    polaris_aging_gt_120h: int = 0


def _inbox_paths(paths: list[str]) -> list[str]:
    resolved = paths or sorted(glob.glob(os.path.join("tasks", "INBOX", "*.md")))
    out: list[str] = []
    for p in resolved:
        if os.path.basename(p).upper() == "README.MD":
            continue
        out.append(p)
    return out


def _packet_records(path: str) -> list[v.Packet]:
    with open(path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    packets_header_idx = None
    for i, line in enumerate(all_lines):
        if line.strip() == "## Packets":
            packets_header_idx = i
            break
    if packets_header_idx is None:
        return []

    start_idx = packets_header_idx + 1
    return v._split_packets(all_lines[start_idx:], start_line_offset=start_idx)


def _is_terminal_result(pkt: v.Packet) -> bool:
    status_re = re.compile(r"^\s*-?\s*Status:\s*(OK|FAILED|BLOCKED)\b", re.IGNORECASE)
    return any(status_re.match(line.strip()) for line in pkt.lines)


def _opened_days(fields: dict[str, str], today: dt.date) -> int | None:
    opened = fields.get("Opened", "").strip()
    if not opened:
        return None
    try:
        opened_date = dt.date.fromisoformat(opened)
    except ValueError:
        return None
    return (today - opened_date).days


def _is_kalshi_policy_risk_packet(pkt: v.Packet) -> bool:
    text = "\n".join(pkt.lines).lower()
    if "kalshi" not in text:
        return False
    return any(token in text for token in ("policy", "risk", "parameter"))


def run_audit(paths: list[str]) -> tuple[AuditTotals, list[str]]:
    totals = AuditTotals()
    findings: list[str] = []
    today = dt.date.today()

    inboxes = _inbox_paths(paths)
    totals.inbox_files = len(inboxes)

    for path in inboxes:
        validation_errors = v.validate_inbox_file(path)
        for err in validation_errors:
            if any(marker in err for marker in MISROUTE_MARKERS):
                totals.misroutes_or_requester_violations += 1
                findings.append(f"MISROUTE: {err}")

        for pkt in _packet_records(path):
            totals.packets_scanned += 1
            fields, _ = v._parse_packet(pkt)
            is_terminal = _is_terminal_result(pkt)

            if os.path.basename(path).upper() == "POLARIS.MD" and not is_terminal:
                totals.polaris_active += 1
                age_days = _opened_days(fields, today)
                if age_days is not None:
                    totals.polaris_oldest_days = max(totals.polaris_oldest_days, age_days)
                    if age_days > 1:
                        totals.polaris_aging_gt_24h += 1
                    if age_days > 2:
                        totals.polaris_aging_gt_48h += 1
                    if age_days > 3:
                        totals.polaris_aging_gt_72h += 1
                    if age_days > 5:
                        totals.polaris_aging_gt_120h += 1

            if _is_kalshi_policy_risk_packet(pkt):
                gate = fields.get("Approval Gate", "").strip()
                evidence = fields.get("Gate Evidence", "").strip()
                if not gate or not evidence:
                    totals.kalshi_gate_misses += 1
                    findings.append(
                        f"GATE_MISS: {path}:{pkt.start_line}: missing "
                        f"{'Approval Gate' if not gate else ''}"
                        f"{' and ' if (not gate and not evidence) else ''}"
                        f"{'Gate Evidence' if not evidence else ''}"
                    )

            notify = fields.get("Notify", "").strip().lower()
            if notify and notify != "none" and not is_terminal:
                totals.notification_noise += 1
                findings.append(f"NOTIFY_NO_RESULT: {path}:{pkt.start_line}")

    return totals, findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly routing audit for Task Packets.")
    ap.add_argument("paths", nargs="*", help="Inbox file paths. Default: tasks/INBOX/*.md")
    ap.add_argument("--verbose", action="store_true", help="Print matching findings.")
    args = ap.parse_args()

    totals, findings = run_audit(args.paths)

    print("ORION WEEKLY ROUTING AUDIT")
    print(f"inbox_files={totals.inbox_files}")
    print(f"packets_scanned={totals.packets_scanned}")
    print(f"misroutes_or_requester_violations={totals.misroutes_or_requester_violations}")
    print(f"kalshi_gate_misses={totals.kalshi_gate_misses}")
    print(f"notification_noise={totals.notification_noise}")
    print(f"queue={totals.polaris_active}/8 oldest={totals.polaris_oldest_days}d")
    print(
        "aging_bands="
        f">24h:{totals.polaris_aging_gt_24h},"
        f">48h:{totals.polaris_aging_gt_48h},"
        f">72h:{totals.polaris_aging_gt_72h},"
        f">120h:{totals.polaris_aging_gt_120h}"
    )

    if args.verbose and findings:
        print("\nFindings:")
        for item in findings:
            print(f"- {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
