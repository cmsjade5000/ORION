#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Dict, Optional, Tuple


def _repo_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _load_dotenv(path: str) -> None:
    def _try(p: str) -> bool:
        try:
            with open(os.path.expanduser(p), "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if not k:
                        continue
                    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                        v = v[1:-1]
                    if k not in os.environ or os.environ.get(k, "") == "":
                        os.environ[k] = v
            return True
        except Exception:
            return False

    if _try(path):
        return
    if os.path.expanduser(path) != os.path.expanduser("~/.openclaw/.env"):
        _try("~/.openclaw/.env")


def _save_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def _acquire_cycle_lock(lock_path: str, *, stale_after_s: int) -> Tuple[bool, str]:
    now = int(time.time())
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    payload = {"pid": os.getpid(), "ts_unix": now}
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(lock_path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True)
            f.write("\n")
        return True, "acquired"
    except FileExistsError:
        prev = _load_json(lock_path)
        prev_ts = int(prev.get("ts_unix") or 0)
        age = max(0, now - prev_ts) if prev_ts > 0 else 0
        if prev_ts > 0 and age > int(max(30, stale_after_s)):
            try:
                os.remove(lock_path)
            except Exception:
                return False, "lock_stale_remove_failed"
            return _acquire_cycle_lock(lock_path, stale_after_s=stale_after_s)
        return False, "lock_held"
    except Exception:
        return False, "lock_error"


def _release_cycle_lock(lock_path: str) -> None:
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        return


def _notify_state_path(root: str) -> str:
    return os.path.join(root, "tmp", "polymarket_sports_paper", "notify_state.json")


def _notification_signature(*, rc: int, stderr_head: str) -> str:
    return f"rc={int(rc)}|err={str(stderr_head).strip()[:160]}"


def _should_send_error_notification(root: str, *, signature: str, now_unix: int, cooldown_s: int) -> bool:
    st = _load_json(_notify_state_path(root))
    last_sig = str(st.get("last_error_sig") or "")
    last_ts = int(st.get("last_notify_ts") or 0)
    if signature != last_sig:
        return True
    return (now_unix - last_ts) >= int(max(60, cooldown_s))


def _mark_error_notification_sent(root: str, *, signature: str, now_unix: int) -> None:
    _save_json(
        _notify_state_path(root),
        {"last_error_sig": str(signature), "last_notify_ts": int(now_unix)},
    )


def _run_cmd_json(argv: list[str], *, cwd: str, timeout_s: int) -> tuple[int, str, Dict[str, Any]]:
    try:
        p = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=float(timeout_s), check=False)
    except Exception as e:
        return (124, "", {"error": str(e)})
    out = (p.stdout or "").strip()
    obj: Dict[str, Any] = {}
    if out:
        try:
            dec = json.loads(out)
            if isinstance(dec, dict):
                obj = dec
            else:
                obj = {"raw": dec}
        except Exception:
            obj = {"raw_stdout": out[:1000], "raw_stderr": (p.stderr or "")[:1000]}
    if p.returncode != 0 and "error" not in obj:
        obj["raw_stderr"] = (p.stderr or "")[:1000]
    return (int(p.returncode), p.stderr or "", obj)


def _write_status(root: str, *, status: str, detail: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {"ts_unix": int(time.time()), "status": str(status), "detail": str(detail)}
    if isinstance(extra, dict):
        payload.update(extra)
    _save_json(os.path.join(root, "tmp", "polymarket_sports_paper", "last_cycle_status.json"), payload)


def _send_telegram(chat_id: int, text: str, *, cwd: str) -> None:
    try:
        subprocess.run(
            ["bash", "scripts/telegram_send_message.sh", str(int(chat_id)), str(text)],
            cwd=cwd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception:
        return


def _telegram_chat_id() -> Optional[int]:
    raw = os.environ.get("ORION_TELEGRAM_CHAT_ID") or ""
    if raw.strip():
        try:
            return int(raw.strip())
        except Exception:
            pass
    cfg = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        obj = json.load(open(cfg, "r", encoding="utf-8"))
    except Exception:
        return None
    ch = ((obj.get("channels") or {}).get("telegram") or {})
    allow = ch.get("allowFrom") or ch.get("dm", {}).get("allowFrom") or []
    try:
        if isinstance(allow, list) and allow:
            return int(allow[0])
    except Exception:
        return None
    return None


def main() -> int:
    root = _repo_root()
    os.chdir(root)
    _load_dotenv(os.environ.get("OPENCLAW_ENV_PATH", "~/.openclaw/.env"))
    ts = int(time.time())
    out_dir = os.path.join(root, "tmp", "polymarket_sports_paper", "runs")
    os.makedirs(out_dir, exist_ok=True)
    lock_path = os.path.join(root, "tmp", "polymarket_sports_paper", "cycle.lock")
    lock_stale_after_s = _env_int("PM_SPORTS_PAPER_LOCK_STALE_SEC", 600)
    locked, lock_reason = _acquire_cycle_lock(lock_path, stale_after_s=lock_stale_after_s)
    if not locked:
        _write_status(
            root,
            status="skipped_lock",
            detail="sports paper cycle skipped; prior cycle still active",
            extra={"lock_reason": lock_reason},
        )
        return 0

    try:
        argv = [
            "python3",
            "scripts/polymarket_sports_paper.py",
            "trade",
            "--limit",
            str(os.environ.get("PM_SPORTS_PAPER_LIMIT", "30")),
            "--max-pages",
            str(os.environ.get("PM_SPORTS_PAPER_MAX_PAGES", "2")),
            "--yes-sum-max",
            str(os.environ.get("PM_SPORTS_PAPER_YES_SUM_MAX", "0.98")),
            "--no-sum-max",
            str(os.environ.get("PM_SPORTS_PAPER_NO_SUM_MAX", "0.98")),
            "--min-edge-bps",
            str(os.environ.get("PM_SPORTS_PAPER_MIN_EDGE_BPS", "5")),
            "--max-pairs-per-run",
            str(os.environ.get("PM_SPORTS_PAPER_MAX_PAIRS_PER_RUN", "2")),
            "--max-risk-per-side-usd",
            str(os.environ.get("PM_SPORTS_PAPER_MAX_RISK_PER_SIDE_USD", "200")),
            "--max-notional-per-run-usd",
            str(os.environ.get("PM_SPORTS_PAPER_MAX_NOTIONAL_PER_RUN_USD", "500")),
            "--max-shares-per-side",
            str(os.environ.get("PM_SPORTS_PAPER_MAX_SHARES_PER_SIDE", "500")),
            "--min-shares",
            str(os.environ.get("PM_SPORTS_PAPER_MIN_SHARES", "1")),
            "--slippage-bps",
            str(os.environ.get("PM_SPORTS_PAPER_SLIPPAGE_BPS", "8")),
            "--latency-ms",
            str(os.environ.get("PM_SPORTS_PAPER_LATENCY_MS", "40")),
            "--sleep-ms",
            str(os.environ.get("PM_SPORTS_PAPER_SLEEP_MS", "25")),
        ]
        timeout_s = _env_int("PM_SPORTS_PAPER_TIMEOUT_S", 120)
        t0 = time.time()
        rc, stderr, trade = _run_cmd_json(argv, cwd=root, timeout_s=timeout_s)
        elapsed_s = round(time.time() - t0, 3)
        stderr_head = str(stderr).strip()[:300]
        artifact = {
            "ts_unix": int(ts),
            "cycle_inputs": {"paper_only": True, "argv": argv[3:], "timeout_s": int(timeout_s)},
            "trade_rc": int(rc),
            "trade": trade if isinstance(trade, dict) else {"raw": trade},
            "stderr_head": stderr_head,
            "elapsed_s": elapsed_s,
        }
        artifact_path = os.path.join(out_dir, f"{ts}.json")
        _save_json(artifact_path, artifact)

        status = "completed" if rc == 0 else "error"
        _write_status(root, status=status, detail="sports paper cycle complete", extra={"artifact": artifact_path, "trade_rc": int(rc)})

        notify_errors = _env_bool("PM_SPORTS_PAPER_NOTIFY_ERRORS", True)
        if rc != 0 and notify_errors:
            cid = _telegram_chat_id()
            sig = _notification_signature(rc=int(rc), stderr_head=stderr_head)
            cooldown_s = _env_int("PM_SPORTS_PAPER_ERROR_NOTIFY_COOLDOWN_S", 900)
            now_unix = int(time.time())
            if cid is not None and _should_send_error_notification(root, signature=sig, now_unix=now_unix, cooldown_s=cooldown_s):
                _send_telegram(
                    int(cid),
                    "\n".join(
                        [
                            "Status: Testing",
                            "What changed:",
                            "- Polymarket sports paper cycle hit an error.",
                            "Why it matters:",
                            "Paper subsystem paused this cycle without any live writes.",
                            "Risks / notes:",
                            "- Check tmp/polymarket_sports_paper/runs for details.",
                            "Next step: Retry automatically on next cycle.",
                        ]
                    ),
                    cwd=root,
                )
                _mark_error_notification_sent(root, signature=sig, now_unix=now_unix)
    finally:
        _release_cycle_lock(lock_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
