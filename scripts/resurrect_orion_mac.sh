#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
default_openclaw="${repo_root}/scripts/openclaww.sh"
OPENCLAW_BIN="${OPENCLAW_BIN:-$default_openclaw}"
GATEWAY_BASE_URL="${ORION_GATEWAY_BASE_URL:-http://127.0.0.1:18789}"
STATE_DIR="${ORION_GATEWAY_GUARD_STATE_DIR:-$HOME/.openclaw/tmp/orion_gateway_guard}"
STATE_FILE="${STATE_DIR}/restart-epochs.log"
SETTLE_SECONDS="${ORION_GATEWAY_SETTLE_SECONDS:-8}"
RESTART_WINDOW_SECONDS="${ORION_GATEWAY_RESTART_WINDOW_SECONDS:-900}"
RESTART_LIMIT="${ORION_GATEWAY_RESTART_LIMIT:-2}"
FORCE_RESTART=0
DO_REPAIR=0

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'TXT'
Usage:
  scripts/resurrect_orion_mac.sh [--force-restart] [--repair]

Default behavior:
  - Perform a lightweight, corroborated gateway health check.
  - Restart the OpenClaw gateway only when the local service is clearly unhealthy.
  - Rate-limit restarts to avoid flapping.

Options:
  --force-restart  Restart even if the gateway looks healthy.
  --repair         Run `openclaw doctor --repair --non-interactive` after restart.
  -h, --help       Show this help.
TXT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-restart)
      FORCE_RESTART=1
      shift
      ;;
    --repair)
      DO_REPAIR=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

probe_http() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 5 "$url" >/dev/null
    return $?
  fi
  python3 - "$url" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        raise SystemExit(0 if 200 <= getattr(resp, "status", 0) < 300 else 1)
except Exception:
    raise SystemExit(1)
PY
}

record_restart_or_block() {
  local now
  now="$(date +%s)"
  mkdir -p "$STATE_DIR"
  python3 - "$STATE_FILE" "$now" "$RESTART_WINDOW_SECONDS" "$RESTART_LIMIT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
now = int(sys.argv[2])
window = int(sys.argv[3])
limit = int(sys.argv[4])

kept: list[int] = []
if path.exists():
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ts = int(raw)
        except ValueError:
            continue
        if now - ts <= window:
            kept.append(ts)

if len(kept) >= limit:
    print(len(kept))
    raise SystemExit(1)

kept.append(now)
path.write_text("".join(f"{ts}\n" for ts in kept), encoding="utf-8")
print(len(kept))
PY
}

gateway_state() {
  local tmp
  tmp="$(mktemp)"
  local status_rc=0
  if ! "$OPENCLAW_BIN" gateway status --json >"$tmp" 2>/dev/null; then
    status_rc=$?
  fi

  local loaded runtime rpc
  if [[ "$status_rc" -eq 0 ]]; then
    eval "$(
      python3 - "$tmp" <<'PY'
import json
import shlex
import sys

data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
service = data.get("service") or {}
runtime = service.get("runtime") or {}
rpc = (data.get("rpc") or {}).get("ok")
runtime_status = str(runtime.get("status") or "").strip().lower() or "unknown"
if rpc is True:
    rpc_status = "1"
elif rpc is False:
    rpc_status = "0"
else:
    rpc_status = "unknown"
print(f"loaded={'1' if service.get('loaded') else '0'}")
print(f"runtime={shlex.quote(runtime_status)}")
print(f"rpc={shlex.quote(rpc_status)}")
PY
    )"
  else
    loaded=0
    runtime="unknown"
    rpc="unknown"
  fi
  rm -f "$tmp"

  local port_listening=0
  if lsof -nP -iTCP:18789 -sTCP:LISTEN >/dev/null 2>&1; then
    port_listening=1
  fi

  local readyz=0
  local healthz=0
  probe_http "${GATEWAY_BASE_URL%/}/readyz" && readyz=1 || true
  probe_http "${GATEWAY_BASE_URL%/}/healthz" && healthz=1 || true

  local classification="degraded"
  if [[ "$loaded" == "1" && "$runtime" == "running" && "$port_listening" == "1" ]]; then
    if [[ "$rpc" == "1" || "$readyz" == "1" || "$healthz" == "1" ]]; then
      classification="healthy"
    elif [[ "$rpc" == "0" && "$readyz" == "0" && "$healthz" == "0" ]]; then
      classification="failed"
    fi
  else
    classification="failed"
  fi

  printf 'classification=%s loaded=%s runtime=%s rpc=%s port=%s readyz=%s healthz=%s\n' \
    "$classification" "$loaded" "$runtime" "$rpc" "$port_listening" "$readyz" "$healthz"
}

restart_gateway() {
  log "Restarting OpenClaw gateway"
  if ! "$OPENCLAW_BIN" gateway restart; then
    log "Gateway restart failed; reinstalling service and starting fresh"
    "$OPENCLAW_BIN" gateway install
    "$OPENCLAW_BIN" gateway start
  fi
  if [[ "$DO_REPAIR" == "1" ]]; then
    log "Running post-restart doctor repair"
    "$OPENCLAW_BIN" doctor --repair --non-interactive || true
  fi
}

log "ORION gateway guard starting"
before_state="$(gateway_state)"
log "Pre-check: ${before_state}"

if [[ "$FORCE_RESTART" != "1" && "$before_state" == classification=healthy* ]]; then
  log "Gateway already healthy; no action needed"
  exit 0
fi

if [[ "$FORCE_RESTART" != "1" && "$before_state" == classification=degraded* ]]; then
  log "Gateway degraded but still serving local probes; skipping automatic restart"
  exit 0
fi

if ! restart_count="$(record_restart_or_block)"; then
  log "Restart guard active; skipping automatic recovery"
  exit 1
fi

log "Restart budget usage in current window: ${restart_count}/${RESTART_LIMIT}"
restart_gateway
sleep "$SETTLE_SECONDS"

after_state="$(gateway_state)"
log "Post-check: ${after_state}"

if [[ "$after_state" == classification=healthy* || "$after_state" == classification=degraded* ]]; then
  log "Gateway recovery complete"
  exit 0
fi

log "Gateway still unhealthy after restart"
exit 1
