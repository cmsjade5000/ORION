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
    from inbox_state import load_kv_state, save_kv_state, sha256_lines
    from inbox_file_ops import atomic_write_text, ensure_packets_header, locked_file, packet_identity
except Exception:  # pragma: no cover
    from scripts.inbox_state import load_kv_state, save_kv_state, sha256_lines  # type: ignore
    from scripts.inbox_file_ops import atomic_write_text, ensure_packets_header, locked_file, packet_identity  # type: ignore


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

def _packet_before_result(packet_lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in packet_lines:
        if ln.strip() == "Result:":
            break
        out.append(ln)
    return out


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

def _parse_int(raw: str, default: int) -> int:
    try:
        return int(str(raw).strip())
    except Exception:
        return default

def _parse_float(raw: str, default: float) -> float:
    try:
        return float(str(raw).strip())
    except Exception:
        return default


def _retry_params(fields: dict[str, str]) -> tuple[int, float, float, float]:
    """
    Return (max_attempts, base_backoff_s, multiplier, max_backoff_s).

    Defaults keep current behavior: 1 attempt and no retries.
    """
    max_attempts = max(1, _parse_int(fields.get("Retry Max Attempts", ""), 1))
    base = max(0.0, _parse_float(fields.get("Retry Backoff Seconds", ""), 60.0))
    mult = max(1.0, _parse_float(fields.get("Retry Backoff Multiplier", ""), 2.0))
    maxb = max(base, _parse_float(fields.get("Retry Max Backoff Seconds", ""), 3600.0))
    return max_attempts, base, mult, maxb


def _command_timeout_seconds(fields: dict[str, str]) -> float:
    default_timeout = max(1.0, _parse_float(os.environ.get("INBOX_RUNNER_CMD_TIMEOUT_S", ""), 120.0))
    configured = _parse_float(fields.get("Command Timeout Seconds", ""), default_timeout)
    return max(1.0, configured)


def _idempotency_fingerprint(fields: dict[str, str], pkt_before_result: list[str]) -> str:
    """
    Stable dedupe key for runner-backed packets.

    If a packet includes an explicit `Idempotency Key:`, prefer it.
    Otherwise fall back to the sha256 of the packet content (before Result).
    """
    raw = (fields.get("Idempotency Key", "") or "").strip()
    if raw:
        return "ik:" + hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    return "ph:" + sha256_lines(pkt_before_result)


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


def _process_one_packet(repo_root: Path, pref: PacketRef, *, state_path: Path) -> bool:
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

    # Retry policy (best-effort). Default is max_attempts=1 (no retry).
    now = time.time()
    max_attempts, base_backoff, mult, max_backoff = _retry_params(fields)
    before = _packet_before_result(pref.raw_lines)
    fp = _idempotency_fingerprint(fields, before)
    attempts_key = f"attempts:{fp}"
    next_key = f"next_allowed:{fp}"
    done_key = f"done:{fp}"
    state0 = load_kv_state(state_path)
    if state0.get(done_key, 0.0) > 0:
        return False
    attempts = int(state0.get(attempts_key, 0.0))
    next_allowed = float(state0.get(next_key, 0.0))
    if next_allowed and now < next_allowed:
        return False

    combined_out: list[str] = []
    combined_err: list[str] = []
    ok = True
    command_timeout_s = _command_timeout_seconds(fields)

    for argv in argv_list:
        try:
            proc = subprocess.run(
                argv,
                cwd=str(repo_root),
                text=True,
                capture_output=True,
                env={**os.environ},
                timeout=command_timeout_s,
            )
            combined_out.append(proc.stdout or "")
            combined_err.append(proc.stderr or "")
            if proc.returncode != 0:
                ok = False
        except subprocess.TimeoutExpired as exc:
            ok = False
            timeout_out = exc.stdout if isinstance(exc.stdout, str) else ""
            timeout_err = exc.stderr if isinstance(exc.stderr, str) else ""
            combined_out.append(timeout_out)
            msg = f"command timed out after {command_timeout_s:.1f}s: {' '.join(argv)}"
            combined_err.append((timeout_err + "\n" if timeout_err else "") + msg + "\n")
            break

    # Persist retry state on failure. If we still have retries left, do NOT write a Result block yet.
    if not ok:
        attempts += 1
        state = load_kv_state(state_path)
        state[attempts_key] = float(attempts)
        if attempts < max_attempts:
            backoff = min(max_backoff, base_backoff * (mult ** max(0, attempts - 1)))
            state[next_key] = float(now + backoff)
            # Keep state bounded.
            if len(state) > 8000:
                state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:6000])
            save_kv_state(state_path, state)
            return True
        # Exhausted retries: fall through and write a Result block.
        state[next_key] = 0.0
        if len(state) > 8000:
            state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:6000])
        save_kv_state(state_path, state)

    stdout = "\n".join([s for s in combined_out if s]).strip() + ("\n" if any(combined_out) else "")
    stderr = "\n".join([s for s in combined_err if s]).strip() + ("\n" if any(combined_err) else "")

    artifact = _write_artifact(repo_root, owner, pref.packet_start_line, stdout, stderr)
    findings = _extract_findings(stdout, stderr)
    artifact_rel = str(artifact.relative_to(repo_root))

    result_block = _format_result_block(ok=ok, findings=findings, artifact_rel=artifact_rel)
    identity = packet_identity(fields=pref.fields, packet_before_result=before)
    lock_path = pref.inbox_path.with_suffix(pref.inbox_path.suffix + ".lock")

    with locked_file(lock_path):
        file_lines = ensure_packets_header(_read_lines(pref.inbox_path), owner=pref.inbox_path.stem.upper())
        packets_header_idx = None
        for i, line in enumerate(file_lines):
            if line.strip() == "## Packets":
                packets_header_idx = i
                break
        if packets_header_idx is None:
            return False
        packet_blocks = _split_packets(file_lines[packets_header_idx + 1 :])
        matched_bounds = None
        for start_idx, end_idx, pkt_lines in packet_blocks:
            candidate_fields = _parse_fields(pkt_lines)
            candidate_before = _packet_before_result(pkt_lines)
            candidate_identity = packet_identity(fields=candidate_fields, packet_before_result=candidate_before)
            if identity.idempotency_key:
                if candidate_identity.idempotency_key != identity.idempotency_key:
                    continue
            elif candidate_identity.content_hash != identity.content_hash:
                continue
            matched_bounds = ((packets_header_idx + 1) + start_idx, (packets_header_idx + 1) + end_idx, pkt_lines)
            break
        if matched_bounds is None:
            return False

        packet_start, packet_end, packet_lines = matched_bounds
        result_idx = None
        for idx, line in enumerate(packet_lines):
            if line.strip() == "Result:":
                result_idx = packet_start + idx
                break
        if result_idx is None:
            new_lines = file_lines[:packet_end] + result_block + file_lines[packet_end:]
        else:
            new_lines = file_lines[:result_idx] + result_block + file_lines[packet_end:]
        atomic_write_text(pref.inbox_path, "\n".join(new_lines).rstrip() + "\n")

    # Mark as done in runner state so re-filed packets with the same Idempotency Key do not repeat work.
    state = load_kv_state(state_path)
    state[done_key] = float(time.time())
    if len(state) > 8000:
        state = dict(sorted(state.items(), key=lambda kv: kv[1], reverse=True)[:6000])
    save_kv_state(state_path, state)
    return True


def run(repo_root: Path, *, max_packets: int, state_path: Path | None = None) -> int:
    # Backward-compatible default for tests/callers that didn't pass state_path.
    if state_path is None:
        state_path = (repo_root / "tmp" / "inbox_runner_state.json").resolve()
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

            if _process_one_packet(repo_root, pref, state_path=state_path):
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
    ap.add_argument(
        "--state-path",
        default="tmp/inbox_runner_state.json",
        help="State file path for retries/backoff (default: tmp/inbox_runner_state.json)",
    )
    args = ap.parse_args()
    repo_root = Path(args.repo_root).resolve()
    state_path = (repo_root / args.state_path).resolve()
    return run(repo_root, max_packets=max(1, int(args.max_packets)), state_path=state_path)


if __name__ == "__main__":
    raise SystemExit(main())
