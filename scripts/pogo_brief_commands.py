#!/usr/bin/env python3
"""Telegram-friendly text commands for Pokemon GO briefing."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_SCRIPT = ROOT / "scripts" / "pogo_brief_inputs.sh"
SENDER_SCRIPT = ROOT / "scripts" / "pogo_morning_voice_send.sh"
CACHE_PATH = ROOT / "tmp" / "pogo_brief_inputs_cache.json"


def env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        val = float(raw)
    except ValueError:
        return default
    return val if val > 0 else default


INPUT_TIMEOUT_SECONDS = env_float("POGO_INPUT_TIMEOUT_SECONDS", 45.0)
TEXT_INPUT_TIMEOUT_SECONDS = env_float("POGO_TEXT_INPUT_TIMEOUT_SECONDS", 30.0)
SENDER_TIMEOUT_SECONDS = env_float("POGO_SENDER_TIMEOUT_SECONDS", 180.0)
CACHE_MAX_AGE_SECONDS = env_float("POGO_CACHE_MAX_AGE_SECONDS", 6 * 3600.0)


def emit(message: str) -> None:
    sys.stdout.write(json.dumps({"message": message}, ensure_ascii=True) + "\n")


def cache_inputs(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")


def load_cached_inputs() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    age = time.time() - CACHE_PATH.stat().st_mtime
    if age > CACHE_MAX_AGE_SECONDS:
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_inputs(*, timeout_seconds: float | None = None) -> dict:
    run_kwargs = dict(
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if timeout_seconds and timeout_seconds > 0:
        run_kwargs["timeout"] = timeout_seconds
    try:
        proc = subprocess.run([str(INPUT_SCRIPT)], **run_kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"timed out after {int(timeout_seconds or 0)}s") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error").strip()
        raise RuntimeError(err)
    out = json.loads(proc.stdout)
    cache_inputs(out)
    return out


def first_title(items: list[dict], fallback: str) -> str:
    if not items:
        return fallback
    val = items[0].get("title")
    return str(val).strip() if val else fallback


def cmd_help() -> str:
    return "\n".join(
        [
            "Pokemon GO quick commands:",
            "- /pogo_voice: send today as voice now",
            "- /pogo_text: send today as text now",
            "- /pogo_today: shiny-first text brief for today",
            "- /pogo_status: freshness + commute + urgency status",
            "- /pogo_help: this command list",
        ]
    )


def cmd_today(data: dict) -> str:
    pokemon = data.get("pokemon", {})
    commute = (data.get("commute", {}) or {}).get("check", {}) or {}
    urgency = data.get("urgency", {}) or {}
    freshness = pokemon.get("freshness", {}) or {}

    shiny = first_title(
        pokemon.get("shinySignals", []) or [],
        "No explicit shiny callout in official cards right now.",
    )
    today_event = first_title(
        pokemon.get("todayEvents", []) or [],
        "No active event card detected today.",
    )

    return "\n".join(
        [
            "Pokemon GO Today (shiny-first)",
            f"Shiny radar: {shiny}",
            f"Today: {today_event}",
            f"Commute: {commute.get('note', 'No commute signal available.')}",
            f"Urgency: {(urgency.get('level') or 'unknown').upper()}",
            f"Intel confidence: {(freshness.get('confidence') or 'unknown').upper()}",
        ]
    )


def cmd_status(data: dict) -> str:
    pokemon = data.get("pokemon", {})
    freshness = pokemon.get("freshness", {}) or {}
    commute = (data.get("commute", {}) or {}).get("check", {}) or {}
    next_shift = (data.get("commute", {}) or {}).get("nextShift")

    shift_line = "none"
    if isinstance(next_shift, dict) and next_shift:
        start = str(next_shift.get("startLocalTime") or next_shift.get("startIso") or "?")
        title = str(next_shift.get("title") or "R096 shift")
        shift_line = f"{title} at {start}"

    age = freshness.get("newsAgeHours")
    age_line = "unknown"
    if isinstance(age, (int, float)):
        age_line = f"{round(float(age), 1)}h"

    return "\n".join(
        [
            "Pokemon GO Brief Status",
            f"Confidence: {(freshness.get('confidence') or 'unknown').upper()} (news age: {age_line})",
            f"Stale feed guard: {'ON' if freshness.get('stale') else 'OFF'}",
            f"Next R096 shift: {shift_line}",
            f"Commute status: {(commute.get('status') or 'unknown').upper()}",
        ]
    )


def run_sender(*sender_args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [str(SENDER_SCRIPT), *sender_args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=SENDER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {int(SENDER_TIMEOUT_SECONDS)}s"
    out = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode, out


def cmd_voice_send() -> str:
    code, out = run_sender("--send")
    if code != 0:
        return f"Pokemon GO voice delivery failed: {out or 'unknown error'}"
    if "SENT_POGO_MORNING_VOICE_OK" in out:
        return "Pokemon GO brief sent as voice."
    if "SENT_POGO_MORNING_TEXT_ONLY_OK" in out:
        return "Requested voice, but sent text-only fallback (TTS unavailable)."
    return f"Pokemon GO send completed: {out or 'ok'}"


def cmd_text_send() -> str:
    # Keep /pogo_text deterministic and fast for Telegram slash handling.
    # The command returns today's text brief directly instead of invoking the
    # full send pipeline, which can be slow/flaky in chat-command contexts.
    try:
        data = load_inputs(timeout_seconds=TEXT_INPUT_TIMEOUT_SECONDS)
        return cmd_today(data)
    except Exception as exc:
        cached = load_cached_inputs()
        if cached:
            return cmd_today(cached) + "\nNote: using cached briefing data while live refresh is unavailable."
        return f"Pokemon GO briefing is temporarily unavailable: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Pokemon GO brief text command helper")
    ap.add_argument("--cmd", choices=["help", "today", "status", "voice", "text"], default="help")
    args = ap.parse_args()

    if args.cmd == "help":
        emit(cmd_help())
        return 0
    if args.cmd == "voice":
        emit(cmd_voice_send())
        return 0
    if args.cmd == "text":
        emit(cmd_text_send())
        return 0

    try:
        data = load_inputs(timeout_seconds=INPUT_TIMEOUT_SECONDS)
    except Exception as exc:  # pragma: no cover - fallback path
        emit(f"Pokemon GO briefing is temporarily unavailable: {exc}")
        return 0

    if args.cmd == "today":
        emit(cmd_today(data))
        return 0
    if args.cmd == "status":
        emit(cmd_status(data))
        return 0

    emit(cmd_help())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
