#!/usr/bin/env python3
"""
Generate a lightweight Post-Incident Review (PIR) draft from an INCIDENT v1 entry.

This is intentionally deterministic and file-based:
- reads tasks/INCIDENTS.md (or provided path)
- extracts one INCIDENT v1 block by Id
- prints a PIR template and follow-up Task Packet drafts
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path


RE_INCIDENT_HEADER = re.compile(r"^INCIDENT v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9 _-]*):\s*(?P<value>.*)\s*$")


@dataclasses.dataclass(frozen=True)
class Incident:
    raw_lines: list[str]
    fields: dict[str, str]
    evidence: list[str]
    actions: list[str]
    followups: list[str]

    @property
    def id(self) -> str:
        return (self.fields.get("Id", "") or "").strip()


def _read_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def split_incidents(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    for ln in lines:
        if RE_INCIDENT_HEADER.match(ln.strip()):
            if cur:
                blocks.append(cur)
            cur = [ln.rstrip("\n")]
            continue
        if cur is not None:
            cur.append(ln.rstrip("\n"))
    if cur:
        blocks.append(cur)
    return blocks


def parse_incident_block(block: list[str]) -> Incident:
    fields: dict[str, str] = {}
    evidence: list[str] = []
    actions: list[str] = []
    followups: list[str] = []

    section: str | None = None
    for ln in block[1:]:
        m = RE_KV.match(ln)
        if m:
            key = m.group("key").strip()
            val = m.group("value").strip()

            if key in {"Evidence", "Actions", "Follow-up Tasks"}:
                section = key
                if val:
                    if section == "Evidence":
                        evidence.append(val)
                    elif section == "Actions":
                        actions.append(val)
                    else:
                        followups.append(val)
                continue

            fields[key] = val
            section = None
            continue

        s = ln.strip()
        if section and s.startswith("- "):
            item = s[2:].strip()
            if section == "Evidence":
                evidence.append(item)
            elif section == "Actions":
                actions.append(item)
            elif section == "Follow-up Tasks":
                followups.append(item)

    return Incident(raw_lines=block, fields=fields, evidence=evidence, actions=actions, followups=followups)


def load_incidents(path: Path) -> list[Incident]:
    lines = _read_lines(path)
    blocks = split_incidents(lines)
    out: list[Incident] = []
    for b in blocks:
        try:
            out.append(parse_incident_block(b))
        except Exception:
            # Be tolerant; ignore malformed entries rather than failing the whole command.
            continue
    return out


def find_incident_by_id(incidents: list[Incident], incident_id: str) -> Incident | None:
    want = (incident_id or "").strip()
    if not want:
        return None
    for it in incidents:
        if it.id == want:
            return it
    return None


def _fmt_list(items: list[str], *, empty: str = "(none)") -> str:
    good = [x for x in items if x.strip() and x.strip() != "(none)"]
    if not good:
        return f"- {empty}"
    return "\n".join([f"- {x}" for x in good])


def render_pir(inc: Incident) -> str:
    opened = inc.fields.get("Opened", "unknown")
    closed = inc.fields.get("Closed", "open")
    sev = inc.fields.get("Severity", "P?")
    trig = inc.fields.get("Trigger", "unknown")
    summary = inc.fields.get("Summary", "(no summary)")
    opened_by = inc.fields.get("Opened By", "unknown")
    follow_owner = inc.fields.get("Follow-up Owner", "ORION") or "ORION"

    # Draft follow-up Task Packet (owner-oriented). This is intentionally generic; ORION/ATLAS
    # can paste it into the appropriate inbox and fill in details.
    tp = "\n".join(
        [
            "TASK_PACKET v1",
            f"Owner: {follow_owner}",
            "Requester: ORION",
            f"Severity: {sev}",
            f"Objective: Produce follow-up actions for incident {inc.id} ({trig}).",
            "Success Criteria:",
            "- Identifies likely root cause(s) and 1-3 prevention actions.",
            "- Produces a concrete validation step to prevent recurrence.",
            "Constraints:",
            "- No secrets. No destructive changes without explicit stop gate approval.",
            "Inputs:",
            f"- Incident: {inc.id}",
            "Risks:",
            "- low",
            "Stop Gates:",
            "- Any destructive command.",
            "- Any credential change.",
            "Output Format:",
            "- Short checklist + any required file paths/diffs.",
        ]
    )

    lines: list[str] = []
    lines.append("PIR v1")
    lines.append(f"Incident: {inc.id}")
    lines.append(f"Severity: {sev}")
    lines.append(f"Trigger: {trig}")
    lines.append(f"Opened: {opened} (by {opened_by})")
    lines.append(f"Closed: {closed}")
    lines.append("")
    lines.append("Summary:")
    lines.append(f"- {summary}")
    lines.append("")
    lines.append("Evidence (from incident log):")
    lines.append(_fmt_list(inc.evidence))
    lines.append("")
    lines.append("Actions Taken (from incident log):")
    lines.append(_fmt_list(inc.actions))
    lines.append("")
    lines.append("What Likely Happened (hypotheses):")
    lines.append("- (fill in) Identify 1-2 likely failure modes, tied to evidence.")
    lines.append("")
    lines.append("Contributing Factors:")
    lines.append("- (fill in) Missing guardrails, drift, missing health checks, unclear ownership, etc.")
    lines.append("")
    lines.append("Immediate Remediation:")
    lines.append("- (fill in) What stops the bleeding now, with rollback notes.")
    lines.append("")
    lines.append("Prevention / Follow-ups:")
    lines.append(_fmt_list(inc.followups, empty="(none recorded)"))
    lines.append("")
    lines.append("Follow-up Task Packet (draft):")
    lines.append("```text")
    lines.append(tp)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate PIR draft text from tasks/INCIDENTS.md.")
    ap.add_argument("incident_id", help="Incident Id (example: INC-YYYYMMDD-hhmm-...)")
    ap.add_argument("--incidents", default="tasks/INCIDENTS.md", help="Incidents file (default: tasks/INCIDENTS.md)")
    args = ap.parse_args()

    p = Path(args.incidents).resolve()
    if not p.exists():
        print(f"ERROR: incidents file not found: {p}", file=sys.stderr)
        return 2

    incidents = load_incidents(p)
    inc = find_incident_by_id(incidents, args.incident_id)
    if not inc:
        print(f"ERROR: incident not found: {args.incident_id}", file=sys.stderr)
        return 1

    print(render_pir(inc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

