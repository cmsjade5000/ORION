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
import mimetypes
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


def _to_artifacts_url(ingest_url: str) -> str:
    s = (ingest_url or "").strip()
    if not s:
        return ""
    suffix = "/api/ingest"
    if s.endswith(suffix):
        return s[: -len(suffix)] + "/api/artifacts"
    return s.rstrip("/") + "/api/artifacts"


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


def upload_artifact(
    file_path: str | Path,
    *,
    name: str | None = None,
    mime: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Best-effort upload of a local file to the Mini App artifact endpoint.

    Returns the `artifact` object from the server response on success, else None.
    """
    ingest_url = _get_ingest_url()
    if not ingest_url:
        return None
    url = _to_artifacts_url(ingest_url)
    if not url:
        return None

    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return None

    data = p.read_bytes()
    fname = (name or p.name or "artifact.bin").strip() or "artifact.bin"
    guessed_mime, _ = mimetypes.guess_type(fname)
    content_type = (mime or guessed_mime or "application/octet-stream").strip() or "application/octet-stream"

    headers: dict[str, str] = {
        "content-type": content_type,
        "x-artifact-name": fname,
    }
    if agent_id:
        headers["x-agent-id"] = str(agent_id).strip()
    tok = _get_ingest_token()
    if tok:
        headers["authorization"] = f"Bearer {tok}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
            if not (200 <= int(resp.status) < 300):
                return None
            obj = json.loads(raw.decode("utf-8", errors="replace"))
            if not isinstance(obj, dict) or obj.get("ok") is not True:
                return None
            art = obj.get("artifact")
            return art if isinstance(art, dict) else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception):
        return None
