#!/usr/bin/env python3
"""
Best-effort client for the Telegram Mini App dashboard ingest endpoint.

This is intentionally optional: if no ingest URL is configured (or ingest fails),
callers should continue normally.

Endpoint contract (server):
- POST { type: string, ts?: number, ... } to /api/ingest
- Optional auth: Authorization: Bearer ${INGEST_TOKEN}
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _get_openclaw_cfg_path() -> Path:
    raw = os.environ.get("OPENCLAW_CONFIG_PATH", "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    return Path.home() / ".openclaw" / "openclaw.json"


def _load_openclaw_env_vars() -> dict[str, str]:
    """
    Best-effort: read ~/.openclaw/openclaw.json and return env.vars as strings.

    This lets LaunchAgents / cron invocations pick up config without having to
    embed secrets in plist files.
    """
    cfg_path = _get_openclaw_cfg_path()
    try:
        obj = json.loads(_read_text(cfg_path))
        env = obj.get("env", {}) if isinstance(obj, dict) else {}
        vars_obj = env.get("vars", {}) if isinstance(env, dict) else {}
        if not isinstance(vars_obj, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in vars_obj.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, str):
                out[k] = v
            elif isinstance(v, (int, float)):
                out[k] = str(v)
        return out
    except Exception:
        return {}


def _coalesce(*vals: str) -> str:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""


def _normalize_ingest_url(base_or_full: str) -> str:
    s = (base_or_full or "").strip().rstrip("/")
    if not s:
        return ""
    if s.endswith("/api/ingest"):
        return s
    return f"{s}/api/ingest"


def _derive_ingest_from_miniapp_url(miniapp_url: str) -> str:
    """
    If only ORION_MINIAPP_URL is configured, try to derive origin + /api/ingest.

    Note: This assumes the dashboard server serves both the web app and /api/ingest.
    If you host them separately, set MINIAPP_INGEST_URL explicitly.
    """
    raw = (miniapp_url or "").strip()
    if not raw:
        return ""
    try:
        from urllib.parse import urlparse

        u = urlparse(raw)
        if not u.scheme or not u.netloc:
            return ""
        return _normalize_ingest_url(f"{u.scheme}://{u.netloc}")
    except Exception:
        return ""


def _get_ingest_url() -> str:
    env_vars = _load_openclaw_env_vars()
    base = _coalesce(
        os.environ.get("MINIAPP_INGEST_URL", ""),
        os.environ.get("ORION_MINIAPP_INGEST_URL", ""),
        env_vars.get("MINIAPP_INGEST_URL", ""),
        env_vars.get("ORION_MINIAPP_INGEST_URL", ""),
    )
    if base:
        return _normalize_ingest_url(base)

    # Fallback: try to derive from the configured Mini App URL.
    miniapp_url = _coalesce(
        os.environ.get("ORION_MINIAPP_URL", ""),
        env_vars.get("ORION_MINIAPP_URL", ""),
    )
    return _derive_ingest_from_miniapp_url(miniapp_url)


def _get_ingest_token() -> str:
    env_vars = _load_openclaw_env_vars()
    return _coalesce(
        os.environ.get("MINIAPP_INGEST_TOKEN", ""),
        os.environ.get("INGEST_TOKEN", ""),
        env_vars.get("MINIAPP_INGEST_TOKEN", ""),
        env_vars.get("INGEST_TOKEN", ""),
    )


def emit_event(body: dict[str, Any]) -> bool:
    """
    Best-effort fire-and-forget emit.
    Returns True if the POST succeeded (2xx), else False.
    """
    url = _get_ingest_url()
    if not url:
        return False

    b = dict(body)
    if "ts" not in b:
        b["ts"] = int(time.time() * 1000)

    data = json.dumps(b, ensure_ascii=True).encode("utf-8")
    headers = {"content-type": "application/json"}
    tok = _get_ingest_token()
    if tok:
        headers["authorization"] = f"Bearer {tok}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            _ = resp.read()
            return 200 <= int(resp.status) < 300
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception):
        # Never block core workflow on dashboard visibility.
        return False


def emit(
    type: str,
    *,
    agentId: str | None = None,
    id: str | None = None,
    text: str | None = None,
    activity: str | None = None,
    extra: dict[str, Any] | None = None,
) -> bool:
    body: dict[str, Any] = {"type": type}
    if agentId:
        body["agentId"] = agentId
    if id:
        body["id"] = id
    if text:
        body["text"] = text
    if activity:
        body["activity"] = activity
    if extra:
        # Keep it JSON-safe; avoid huge payloads.
        body.update(extra)
    return emit_event(body)

