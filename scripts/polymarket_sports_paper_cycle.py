#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Dict, Optional


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

    argv = [
        "python3",
        "scripts/polymarket_sports_paper.py",
        "trade",
        "--limit",
        str(os.environ.get("PM_SPORTS_PAPER_LIMIT", "50")),
        "--max-pages",
        str(os.environ.get("PM_SPORTS_PAPER_MAX_PAGES", "4")),
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
    rc, stderr, trade = _run_cmd_json(argv, cwd=root, timeout_s=int(os.environ.get("PM_SPORTS_PAPER_TIMEOUT_S", "90")))
    artifact = {
        "ts_unix": int(ts),
        "cycle_inputs": {"paper_only": True, "argv": argv[3:]},
        "trade_rc": int(rc),
        "trade": trade if isinstance(trade, dict) else {"raw": trade},
        "stderr_head": str(stderr).strip()[:300],
    }
    artifact_path = os.path.join(out_dir, f"{ts}.json")
    _save_json(artifact_path, artifact)

    status = "completed" if rc == 0 else "error"
    _write_status(root, status=status, detail="sports paper cycle complete", extra={"artifact": artifact_path, "trade_rc": int(rc)})

    if rc != 0 and str(os.environ.get("PM_SPORTS_PAPER_NOTIFY_ERRORS", "1")).strip().lower() in ("1", "true", "yes", "on"):
        cid = _telegram_chat_id()
        if cid is not None:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

