#!/usr/bin/env python3
"""
Deterministic inbox packet runner for a small allowlist of safe, read-only tasks.

Why this exists:
- ORION can create Task Packets for specialists, but those packets may not get executed
  reliably without user "continue" prodding.
- This runner executes an allowlisted subset of packets automatically and writes a
  Result: block back into tasks/INBOX/*.md, which then triggers the notifier.

Security posture:
- Only runs packets that explicitly indicate read-only constraints.
- Only runs packets with `Notify: telegram` or `Notify: discord` (opt-in).
- Only runs allowlisted commands mapped to repo-local scripts (no arbitrary shell).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

try:
    # Optional dependency: Mini App dashboard progress visibility.
    # When executed as `python3 scripts/run_inbox_packets.py`, sys.path[0] is `scripts/`,
    # so `miniapp_ingest` is importable as a sibling module.
    from miniapp_ingest import emit as miniapp_emit
except Exception:  # pragma: no cover
    try:  # pragma: no cover
        # When executed in other ways (e.g. `python3 -c ...` from repo root).
        from scripts.miniapp_ingest import emit as miniapp_emit  # type: ignore
    except Exception:  # pragma: no cover
        def miniapp_emit(*args, **kwargs):  # type: ignore[no-redef]
            return False


RE_PACKET_HEADER = re.compile(r"^TASK_PACKET v1\s*$")
RE_KV = re.compile(r"^(?P<key>[A-Za-z][A-Za-z ]*):\s*(?P<value>.*)\s*$")


ALLOWLIST_COMMANDS: dict[str, list[str]] = {
    # Packet may specify just "diagnose_gateway.sh"; map to the repo script.
    "diagnose_gateway.sh": ["bash", "-lc", "scripts/diagnose_gateway.sh"],
    "./scripts/diagnose_gateway.sh": ["bash", "-lc", "scripts/diagnose_gateway.sh"],
    "scripts/diagnose_gateway.sh": ["bash", "-lc", "scripts/diagnose_gateway.sh"],

    # Multi-agent sanity checks (all read-only).
    "ember_sanity_check.sh": ["bash", "-lc", "scripts/ember_sanity_check.sh"],
    "scripts/ember_sanity_check.sh": ["bash", "-lc", "scripts/ember_sanity_check.sh"],
    "pixel_sanity_check.sh": ["bash", "-lc", "scripts/pixel_sanity_check.sh"],
    "scripts/pixel_sanity_check.sh": ["bash", "-lc", "scripts/pixel_sanity_check.sh"],
    "node_sanity_check.sh": ["bash", "-lc", "scripts/node_sanity_check.sh"],
    "scripts/node_sanity_check.sh": ["bash", "-lc", "scripts/node_sanity_check.sh"],
    "ledger_snapshot.sh": ["bash", "-lc", "scripts/ledger_snapshot.sh"],
    "scripts/ledger_snapshot.sh": ["bash", "-lc", "scripts/ledger_snapshot.sh"],

    # Read-only arb scanning (no trading / no secrets).
    "arb_scan.sh": ["bash", "-lc", "scripts/arb_scan.sh"],
    "./scripts/arb_scan.sh": ["bash", "-lc", "scripts/arb_scan.sh"],
    "scripts/arb_scan.sh": ["bash", "-lc", "scripts/arb_scan.sh"],
}


@dataclasses.dataclass(frozen=True)
class PacketRef:
    inbox_path: Path
    packet_start_line: int
    packet_end_line: int
    fields: dict[str, str]
    raw_lines: list[str]


def _read_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def _split_packets(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    """Return list of (start_idx, end_idx_exclusive, packet_lines) for TASK_PACKET v1 blocks.

    Ignores fenced blocks (```).
    """

    in_fence = False
    starts: list[int] = []
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and RE_PACKET_HEADER.match(line):
            starts.append(i)

    out: list[tuple[int, int, list[str]]] = []
    for si, s in enumerate(starts):
        e = starts[si + 1] if si + 1 < len(starts) else len(lines)
        out.append((s, e, lines[s:e]))
    return out


def _parse_fields(packet_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in packet_lines[1:]:
        m = RE_KV.match(line)
        if not m:
            continue
        fields[m.group("key").strip()] = m.group("value").strip()
    return fields


def _packet_has_result(packet_lines: list[str]) -> bool:
    """
    Consider a packet "done" only if there is a non-empty Result section.

    ORION sometimes pre-creates an empty `Result:` placeholder; we treat that as pending.
    """
    start = None
    for i, ln in enumerate(packet_lines):
        if ln.strip() == "Result:":
            start = i
            break
    if start is None:
        return False
    return any(ln.strip() for ln in packet_lines[start + 1 :])


def _packet_is_read_only(packet_lines: list[str]) -> bool:
    txt = "\n".join(packet_lines).lower()
    return ("read-only" in txt) or ("readonly" in txt)


def _extract_commands(packet_lines: list[str]) -> list[str]:
    """Extract bullet commands listed under a "Commands to run:" header."""

    cmds: list[str] = []
    in_section = False
    for raw in packet_lines:
        line = raw.rstrip("\n")
        if not in_section:
            s = line.strip()
            if s.startswith("Commands to run:"):
                # Support both:
                # - "Commands to run:" + bullet list
                # - "Commands to run: diagnose_gateway.sh" (single-line)
                tail = s[len("Commands to run:") :].strip()
                if tail:
                    cmds.append(tail)
                    break
                in_section = True
            continue

        # Stop once we hit a new key/value or a new header-like section.
        if RE_KV.match(line) and not line.lstrip().startswith(("-", "*")):
            break
        if line.strip().endswith(":") and not line.lstrip().startswith(("-", "*")):
            break

        s = line.strip()
        if s.startswith("- "):
            cmds.append(s[2:].strip())
        elif s.startswith("* "):
            cmds.append(s[2:].strip())

    return [c for c in cmds if c]


def _safe_command_argv(cmd: str) -> list[str] | None:
    # Exact allowlist only.
    return ALLOWLIST_COMMANDS.get(cmd)


def _write_artifact(repo_root: Path, owner: str, packet_start_line: int, stdout: str, stderr: str) -> Path:
    out_dir = repo_root / "tmp" / "inbox_runner" / owner
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    h = hashlib.sha256(f"{owner}:{packet_start_line}:{ts}".encode("utf-8")).hexdigest()[:10]
    p = out_dir / f"{ts}-{packet_start_line}-{h}.log"

    body = stdout or ""
    if body and not body.endswith("\n"):
        body += "\n"
    if stderr:
        body += "[stderr]\n" + stderr
        if not body.endswith("\n"):
            body += "\n"

    p.write_text(body, encoding="utf-8")
    return p


def _extract_findings(stdout: str, stderr: str) -> list[str]:
    # Keep it short and useful; diagnose script already redacts secrets.
    important_prefixes = (
        "Telegram:",
        "Slack:",
        "Mochat:",
        "Agents:",
        "Heartbeat interval:",
        "Session store",
        "Gateway target:",
    )

    findings: list[str] = []
    for ln in (stdout.splitlines() + stderr.splitlines()):
        s = ln.strip()
        if not s:
            continue
        if any(s.startswith(p) for p in important_prefixes):
            findings.append(s)
        if ("error" in s.lower() or "failed" in s.lower()) and s not in findings:
            findings.append(s)
        if len(findings) >= 10:
            break

    if findings:
        return findings

    excerpt = [ln.strip() for ln in stdout.splitlines() if ln.strip()][:8]
    return excerpt if excerpt else ["(No notable output.)"]


def _format_result_block(*, ok: bool, findings: list[str], artifact_rel: str) -> list[str]:
    status = "OK" if ok else "FAILED"
    lines: list[str] = []
    lines.append("")
    lines.append("Result:")
    lines.append(f"Status: {status}")
    lines.append("Findings:")
    for f in findings:
        lines.append(f"  - {f}")
    lines.append("Artifacts:")
    lines.append(f"  - {artifact_rel}")
    lines.append("Next step (if any):")
    lines.append("  - None." if ok else "  - Inspect the artifact log above; re-run if needed.")
    lines.append("")
    return lines


def _process_one_packet(repo_root: Path, pref: PacketRef) -> bool:
    fields = pref.fields
    owner = (fields.get("Owner", "").strip() or pref.inbox_path.stem).upper()
    notify = fields.get("Notify", "").strip().lower()

    if notify not in {"telegram", "discord"}:
        return False
    if not _packet_is_read_only(pref.raw_lines):
        return False

    cmds = _extract_commands(pref.raw_lines)
    if not cmds:
        return False

    argv_list: list[list[str]] = []
    for c in cmds:
        argv = _safe_command_argv(c)
        if not argv:
            return False
        argv_list.append(argv)

    # Mini App progress visibility: mark the specialist as starting work.
    # Best-effort only; failures should not affect execution.
    miniapp_emit("task.started", agentId=owner, extra={"source": "inbox_runner"})

    combined_out: list[str] = []
    combined_err: list[str] = []
    ok = True

    for argv in argv_list:
        miniapp_emit(
            "tool.started",
            agentId=owner,
            extra={"source": "inbox_runner", "tool": " ".join(argv[:4])},
        )
        proc = subprocess.run(
            argv,
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            env={**os.environ},
        )
        combined_out.append(proc.stdout or "")
        combined_err.append(proc.stderr or "")
        if proc.returncode != 0:
            ok = False
            miniapp_emit(
                "tool.failed",
                agentId=owner,
                extra={"source": "inbox_runner", "code": int(proc.returncode)},
            )
        else:
            miniapp_emit("tool.finished", agentId=owner, extra={"source": "inbox_runner", "code": 0})

    stdout = "\n".join([s for s in combined_out if s]).strip() + ("\n" if any(combined_out) else "")
    stderr = "\n".join([s for s in combined_err if s]).strip() + ("\n" if any(combined_err) else "")

    artifact = _write_artifact(repo_root, owner, pref.packet_start_line, stdout, stderr)
    findings = _extract_findings(stdout, stderr)
    artifact_rel = str(artifact.relative_to(repo_root))
    result_block = _format_result_block(ok=ok, findings=findings, artifact_rel=artifact_rel)

    # Insert/replace the Result block.
    file_lines = _read_lines(pref.inbox_path)
    # If the packet already contains a `Result:` placeholder, replace it to avoid duplicate Result sections.
    result_idx = None
    for i in range(pref.packet_start_line - 1, pref.packet_end_line):
        if file_lines[i].strip() == "Result:":
            result_idx = i
            break

    if result_idx is None:
        insert_at = pref.packet_end_line
        new_lines = file_lines[:insert_at] + result_block + file_lines[insert_at:]
    else:
        new_lines = file_lines[:result_idx] + result_block + file_lines[pref.packet_end_line :]
    pref.inbox_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")

    # Final Mini App state + a short feed item so opening the Mini App after completion
    # still shows something meaningful even if the agent node has gone idle.
    miniapp_emit("task.completed" if ok else "task.failed", agentId=owner, extra={"source": "inbox_runner"})
    # Stable id to avoid duplicates if multiple components emit the same completion.
    key = f"{pref.inbox_path.resolve().as_posix()}:{pref.packet_start_line}"
    rid = f"pktres_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"
    miniapp_emit(
        "response.created",
        agentId=owner,
        id=rid,
        text=f"[{owner}] {fields.get('Objective','(no objective)') or '(no objective)'} -> {'OK' if ok else 'FAILED'}",
        extra={"source": "inbox_runner"},
    )
    return True


def run(repo_root: Path, *, max_packets: int) -> int:
    inbox_dir = repo_root / "tasks" / "INBOX"
    if not inbox_dir.exists():
        print("RUNNER_NO_INBOX")
        return 0

    processed = 0
    for inbox in sorted(inbox_dir.glob("*.md")):
        if inbox.name.upper() == "README.MD":
            continue

        lines = _read_lines(inbox)

        # Only scan packets appended under "## Packets" to avoid examples/notes.
        packets_header_idx = None
        for i, line in enumerate(lines):
            if line.strip() == "## Packets":
                packets_header_idx = i
                break
        if packets_header_idx is None:
            continue

        packets = _split_packets(lines[packets_header_idx + 1 :])
        for start_idx, end_idx, pkt_lines in packets:
            if _packet_has_result(pkt_lines):
                continue

            pref = PacketRef(
                inbox_path=inbox,
                packet_start_line=(packets_header_idx + 1) + start_idx + 1,
                packet_end_line=(packets_header_idx + 1) + end_idx,
                fields=_parse_fields(pkt_lines),
                raw_lines=pkt_lines,
            )

            if _process_one_packet(repo_root, pref):
                processed += 1
                if processed >= max_packets:
                    print(f"RUNNER_OK processed={processed}")
                    return 0

    print("RUNNER_IDLE" if processed == 0 else f"RUNNER_OK processed={processed}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run allowlisted inbox task packets and write Result blocks.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--max-packets", type=int, default=1, help="Max packets to process per run (default: 1)")
    args = ap.parse_args()
    return run(Path(args.repo_root).resolve(), max_packets=max(1, int(args.max_packets)))


if __name__ == "__main__":
    raise SystemExit(main())
