#!/usr/bin/env python3
"""Publish versioned Arc Raiders Field Guide drafts to Discord threads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPENCLAW_BIN = (
    os.environ.get("OPENCLAW_BIN")
    or shutil.which("openclaw")
    or "/Users/corystoner/.npm-global/bin/openclaw"
)

DOC_SPECS = [
    {
        "key": "chapters_layout",
        "label": "Chapters/Layout",
        "thread_name": "FG-Chapters-Layout",
        "source_relpath": "docs/arc-raiders-field-guide/chapters-layout-draft.md",
    },
    {
        "key": "cost_breakdown",
        "label": "Cost Breakdown",
        "thread_name": "FG-Cost-Breakdown",
        "source_relpath": "docs/arc-raiders-field-guide/cost-breakdown-draft.md",
    },
    {
        "key": "project_management",
        "label": "Project Management",
        "thread_name": "FG-Project-Management",
        "source_relpath": "docs/arc-raiders-field-guide/project-management-draft.md",
    },
]


def now_local_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def now_utc_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_cmd(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def minutes_since(ts: str | None, now_dt: datetime) -> float | None:
    dt = parse_iso(ts)
    if not dt:
        return None
    return (now_dt - dt).total_seconds() / 60.0


def thread_id_by_name(registry: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in registry.get("threads") or []:
        name = t.get("name")
        tid = t.get("id")
        if name and tid:
            out[name] = str(tid)
    return out


def send_discord_message(
    *,
    target: str,
    message: str,
    media_path: Path | None,
    dry_run: bool,
) -> dict[str, Any]:
    cmd = [
        OPENCLAW_BIN,
        "message",
        "send",
        "--channel",
        "discord",
        "--target",
        target,
        "--message",
        message,
        "--json",
    ]
    if media_path is not None:
        cmd.extend(["--media", str(media_path)])
    if dry_run:
        cmd.append("--dry-run")
    raw = run_cmd(cmd)
    return json.loads(raw)


def snapshot_text_header(
    *,
    label: str,
    source_path: Path,
    source_hash: str,
    version: int,
    created_at: str,
) -> str:
    return (
        "<!-- ARC FG Snapshot\n"
        f"label: {label}\n"
        f"source_path: {source_path}\n"
        f"source_sha256: {source_hash}\n"
        f"version: {version}\n"
        f"created_at: {created_at}\n"
        "-->\n\n"
    )


def write_snapshot(
    *,
    out_dir: Path,
    key: str,
    source_text: str,
    header: str,
    version: int,
    stamp: str,
) -> Path:
    safe_key = key.replace("_", "-")
    out_name = f"arc-fg-{safe_key}-v{version:04d}-{stamp}.md"
    out_path = out_dir / out_name
    out_path.write_text(header + source_text)
    return out_path


def convert_md_to_docx(md_path: Path) -> Path:
    docx_path = md_path.with_suffix(".docx")
    cmd = [
        "/usr/bin/textutil",
        "-convert",
        "docx",
        "-output",
        str(docx_path),
        str(md_path),
    ]
    run_cmd(cmd)
    return docx_path


def extract_message_id(result: dict[str, Any]) -> str | None:
    payload = result.get("payload") or {}
    nested = payload.get("result") or {}
    mid = nested.get("messageId")
    return str(mid) if mid else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Arc FG draft snapshots to Discord.")
    parser.add_argument("--registry", default="tmp/arc_fg_thread_registry.json")
    parser.add_argument("--state", default="tmp/arc_fg_loop_state.json")
    parser.add_argument("--out-dir", default="~/.openclaw/media/outbound/arc_fg_versions")
    parser.add_argument("--min-interval-minutes", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cwd = Path.cwd()
    state_path = (cwd / args.state).resolve()
    registry_path = (cwd / args.registry).resolve()
    out_dir_root = Path(args.out_dir).expanduser()
    if not out_dir_root.is_absolute():
        out_dir_root = (cwd / out_dir_root).resolve()
    out_dir = out_dir_root / datetime.now().astimezone().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)

    state = load_json(state_path, {"version": 1, "updated_at": now_local_iso(), "active_run": None})
    registry = load_json(registry_path, {})
    now_dt = datetime.now().astimezone()
    now_iso = now_dt.replace(microsecond=0).isoformat()
    stamp = now_utc_compact()

    pub = state.setdefault("doc_publisher", {})
    pub_docs = pub.setdefault("docs", {})
    pub["checked_at"] = now_iso
    pub["min_interval_minutes"] = args.min_interval_minutes
    pub["dry_run"] = bool(args.dry_run)

    if state.get("active_run"):
        pub["status"] = "skip_active_run"
        state["updated_at"] = now_iso
        save_json(state_path, state)
        print(json.dumps({"status": "ok", "action": "skip_active_run"}))
        return 0

    thread_ids = thread_id_by_name(registry)
    hq_thread_id = registry.get("hq_thread_id")
    sent_entries: list[dict[str, Any]] = []
    skipped_entries: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for spec in DOC_SPECS:
        key = spec["key"]
        label = spec["label"]
        source_path = (cwd / spec["source_relpath"]).resolve()
        thread_name = spec["thread_name"]
        target_thread_id = thread_ids.get(thread_name)
        doc_state = pub_docs.setdefault(key, {"version": 0})

        if not source_path.exists():
            errors.append(f"{key}:missing_source:{source_path}")
            continue
        if not target_thread_id:
            errors.append(f"{key}:missing_thread_id:{thread_name}")
            continue

        source_text = source_path.read_text()
        source_hash = sha256_text(source_text)
        last_hash = doc_state.get("last_sent_hash")
        mins = minutes_since(doc_state.get("last_sent_at"), now_dt)
        cooldown_blocked = (
            not args.force
            and mins is not None
            and mins < float(args.min_interval_minutes)
            and source_hash != last_hash
        )

        if not args.force and source_hash == last_hash:
            skipped_entries.append({"key": key, "reason": "unchanged"})
            continue
        if cooldown_blocked:
            skipped_entries.append({"key": key, "reason": "cooldown"})
            continue

        version = int(doc_state.get("version", 0)) + 1
        header = snapshot_text_header(
            label=label,
            source_path=source_path,
            source_hash=source_hash,
            version=version,
            created_at=now_iso,
        )
        snapshot_path = write_snapshot(
            out_dir=out_dir,
            key=key,
            source_text=source_text,
            header=header,
            version=version,
            stamp=stamp,
        )

        artifact_path = snapshot_path
        artifact_kind = "md"
        try:
            docx_path = convert_md_to_docx(snapshot_path)
            artifact_path = docx_path
            artifact_kind = "docx"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{key}:docx_convert_failed:{exc}")

        msg = f"FG {label} · v{version:04d} · {artifact_kind.upper()}"
        try:
            send_result = send_discord_message(
                target=target_thread_id,
                message=msg,
                media_path=artifact_path,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{key}:send_failed:{exc}")
            continue

        msg_id = extract_message_id(send_result)
        if not args.dry_run:
            doc_state["version"] = version
            doc_state["last_sent_at"] = now_iso
            doc_state["last_sent_hash"] = source_hash
            doc_state["last_snapshot_md_path"] = str(snapshot_path)
            doc_state["last_snapshot_docx_path"] = str(snapshot_path.with_suffix(".docx")) if artifact_kind == "docx" else None
            doc_state["last_snapshot_path"] = str(artifact_path)
            doc_state["last_snapshot_format"] = artifact_kind
            doc_state["last_thread_id"] = target_thread_id
            doc_state["last_message_id"] = msg_id
            doc_state["last_send_result"] = send_result

        sent_entries.append(
            {
                "key": key,
                "label": label,
                "thread_name": thread_name,
                "thread_id": target_thread_id,
                "version": version,
                "snapshot_md_path": str(snapshot_path),
                "snapshot_path": str(artifact_path),
                "snapshot_format": artifact_kind,
                "source_hash": source_hash,
                "message_id": msg_id,
            }
        )

    manifest_path: Path | None = None
    if sent_entries and hq_thread_id:
        manifest_lines = [
            "# Arc FG Draft Snapshot Manifest",
            "",
            f"Generated: {now_iso}",
            "",
        ]
        for entry in sent_entries:
            manifest_lines.extend(
                [
                    f"- `{entry['label']}`",
                    f"  - thread_id: `{entry['thread_id']}`",
                    f"  - version: `v{entry['version']:04d}`",
                    f"  - source_hash: `{entry['source_hash'][:12]}`",
                    f"  - format: `{entry['snapshot_format']}`",
                    f"  - snapshot: `{entry['snapshot_path']}`",
                ]
            )
        if skipped_entries:
            manifest_lines.extend(["", "## Skipped", ""])
            for s in skipped_entries:
                manifest_lines.append(f"- `{s['key']}`: {s['reason']}")
        if errors:
            manifest_lines.extend(["", "## Errors", ""])
            for err in errors:
                manifest_lines.append(f"- {err}")
        if warnings:
            manifest_lines.extend(["", "## Warnings", ""])
            for w in warnings:
                manifest_lines.append(f"- {w}")

        manifest_path = out_dir / f"arc-fg-manifest-{stamp}.md"
        manifest_path.write_text("\n".join(manifest_lines) + "\n")

        hq_msg = f"FG Docs Update · {len(sent_entries)} thread attachment(s)"
        try:
            send_discord_message(
                target=str(hq_thread_id),
                message=hq_msg,
                media_path=manifest_path,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"hq_manifest_send_failed:{exc}")

    pub["status"] = "ok" if not errors else "partial_error"
    pub["last_run_at"] = now_iso
    pub["last_sent_count"] = len(sent_entries)
    pub["last_skipped_count"] = len(skipped_entries)
    pub["last_manifest_path"] = str(manifest_path) if manifest_path else None
    pub["last_errors"] = errors
    pub["last_warnings"] = warnings
    state["updated_at"] = now_iso
    save_json(state_path, state)

    result = {
        "status": "ok" if not errors else "error",
        "action": "published" if sent_entries else "skip_no_changes",
        "sent_count": len(sent_entries),
        "skipped_count": len(skipped_entries),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
