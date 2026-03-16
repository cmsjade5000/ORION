#!/usr/bin/env bash
set -euo pipefail

# STRATUS: safe, read-only health check suitable for Task Packets / automation.
#
# Output is intentionally concise and stable:
# - CHECKS: bullet list
# - NEXT: single recommended next step (if any)
#
# Exit codes:
# - 0: gateway health OK
# - 1: gateway health FAIL
# - 2: openclaw missing / usage error

have() { command -v "$1" >/dev/null 2>&1; }

probe_http() {
  local url="$1"
  if have curl; then
    curl -fsS --max-time 5 "$url" >/dev/null
    return $?
  fi
  if have python3; then
    python3 - "$url" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        sys.exit(0 if 200 <= getattr(resp, "status", 0) < 300 else 1)
except Exception:
    sys.exit(1)
PY
    return $?
  fi
  return 2
}

skip_host=0
check_channels=0
app_server_base="${STRATUS_APP_SERVER_BASE_URL:-${CODEX_APP_SERVER_BASE_URL:-}}"
if [[ "${STRATUS_SKIP_HOST:-}" == "1" ]]; then
  skip_host=1
fi
if [[ "${STRATUS_CHECK_CHANNELS:-}" == "1" ]]; then
  check_channels=1
fi

while [[ $# -gt 0 ]]; do
  arg="$1"
  case "$arg" in
    --no-host)
      skip_host=1
      shift
      ;;
    --channels)
      check_channels=1
      shift
      ;;
    --app-server)
      shift
      app_server_base="${1-}"
      if [[ -z "$app_server_base" ]]; then
        printf 'CHECKS:\n'
        printf -- '- app-server: MISSING_URL\n'
        printf 'NEXT:\n'
        printf -- '- Re-run with --app-server URL.\n'
        exit 2
      fi
      shift
      ;;
    --app-server=*)
      app_server_base="${arg#*=}"
      shift
      ;;
    -h|--help)
      cat <<'TXT'
Usage:
  scripts/stratus_healthcheck.sh [--no-host] [--channels] [--app-server URL]

Options:
  --no-host   Skip host resource checks (useful for tests/CI).
  --channels  Probe channel status (slow; includes Slack/Telegram/Mochat).
  --app-server  Probe Codex app-server health on URL via /readyz and /healthz.
TXT
      exit 2
      ;;
    *)
      shift
      ;;
  esac
done

OPENCLAW="${OPENCLAW_BIN:-}"
if [[ -z "${OPENCLAW}" ]]; then
  OPENCLAW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaww.sh"
fi

if [[ ! -x "$OPENCLAW" ]]; then
  if have openclaw; then
    OPENCLAW="openclaw"
  fi
fi

if [[ "$OPENCLAW" == "openclaw" ]]; then
  if ! have openclaw; then
    printf 'CHECKS:\n'
    printf -- '- openclaw: MISSING\n'
    printf 'NEXT:\n'
    printf -- '- Install/open PATH to openclaw.\n'
    exit 2
  fi
elif [[ ! -x "$OPENCLAW" ]]; then
  printf 'CHECKS:\n'
  printf -- '- openclaw: MISSING\n'
  printf 'NEXT:\n'
  printf -- '- Install/open PATH to openclaw.\n'
  exit 2
fi

tmp="${TMPDIR:-/tmp}/stratus_health.$$.$RANDOM.out"
status_json="${TMPDIR:-/tmp}/stratus_status.$$.$RANDOM.json"
trap 'rm -f "$tmp" "$status_json" 2>/dev/null || true' EXIT

health="FAIL"
if "$OPENCLAW" health >"$tmp" 2>&1; then
  health="OK"
fi

gateway_service="UNKNOWN"
gateway_rpc="UNKNOWN"
gateway_config_audit="UNKNOWN"
gateway_overall="UNKNOWN"

if "$OPENCLAW" gateway status --json >"$status_json" 2>/dev/null; then
  parsed="$(
    python3 - "$status_json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path, "r", encoding="utf-8"))
service_loaded = bool(((data.get("service") or {}).get("loaded")))
runtime_status = str((((data.get("service") or {}).get("runtime") or {}).get("status") or "")).strip().lower()
rpc_ok = (data.get("rpc") or {}).get("ok")
config_ok = ((data.get("service") or {}).get("configAudit") or {}).get("ok")
service = "OK" if service_loaded and runtime_status == "running" else "FAIL"
rpc = "OK" if rpc_ok is True else ("DEGRADED" if rpc_ok is False else "UNKNOWN")
cfg = "OK" if config_ok is True else ("DEGRADED" if config_ok is False else "UNKNOWN")
overall = "OK" if service == "OK" and rpc == "OK" and cfg == "OK" else ("FAIL" if service == "FAIL" else "DEGRADED")
print("|".join([service, rpc, cfg, overall]))
PY
  )"
  gateway_service="${parsed%%|*}"
  rest="${parsed#*|}"
  gateway_rpc="${rest%%|*}"
  rest="${rest#*|}"
  gateway_config_audit="${rest%%|*}"
  gateway_overall="${rest##*|}"
else
  if "$OPENCLAW" gateway status >/dev/null 2>&1; then
    gateway_service="OK"
    gateway_overall="OK"
  else
    gateway_service="FAIL"
    gateway_overall="FAIL"
  fi
fi

app_readyz="SKIP"
app_healthz="SKIP"
app_probe_failed=0
if [[ -n "$app_server_base" ]]; then
  app_server_base="${app_server_base%/}"
  if probe_http "${app_server_base}/readyz"; then
    app_readyz="OK"
  else
    app_readyz="FAIL"
    app_probe_failed=1
  fi
  if probe_http "${app_server_base}/healthz"; then
    app_healthz="OK"
  else
    app_healthz="FAIL"
    app_probe_failed=1
  fi
fi

printf 'CHECKS:\n'
printf -- '- gateway health: %s\n' "$health"
printf -- '- gateway service: %s\n' "$gateway_service"
printf -- '- gateway rpc: %s\n' "$gateway_rpc"
printf -- '- gateway config audit: %s\n' "$gateway_config_audit"
printf -- '- gateway overall: %s\n' "$gateway_overall"
if [[ -n "$app_server_base" ]]; then
  printf -- '- codex app-server readyz: %s\n' "$app_readyz"
  printf -- '- codex app-server healthz: %s\n' "$app_healthz"
fi

if [[ "$check_channels" -eq 1 ]]; then
  channels="$("$OPENCLAW" channels status --probe 2>/dev/null || true)"
  if [[ -z "$channels" ]]; then
    printf -- '- channels: UNKNOWN\n'
  else
    norm_line() { printf '%s' "$1" | sed -E 's/^- +//'; }
    # Keep parsing intentionally loose; we just want a quick "is it running?" signal.
    telegram_state="$(printf '%s\n' "$channels" | grep -E '^- Telegram' | head -n 1 || true)"
    slack_state="$(printf '%s\n' "$channels" | grep -E '^- Slack' | head -n 1 || true)"
    mochat_state="$(printf '%s\n' "$channels" | grep -E '^- Mochat' | head -n 1 || true)"
    [[ -n "$telegram_state" ]] && printf -- '- %s\n' "$(norm_line "$telegram_state")"
    [[ -n "$slack_state" ]] && printf -- '- %s\n' "$(norm_line "$slack_state")"
    [[ -n "$mochat_state" ]] && printf -- '- %s\n' "$(norm_line "$mochat_state")"
  fi
fi

if [[ "$skip_host" -eq 0 ]]; then
  # Keep these intentionally lightweight and OS-agnostic.
  disk_line="$(df -h / 2>/dev/null | tail -n 1 || true)"
  if [[ -n "$disk_line" ]]; then
    disk_free="$(printf '%s' "$disk_line" | awk '{print $4}' 2>/dev/null || true)"
    [[ -n "$disk_free" ]] && printf -- '- host disk: %s free on /\n' "$disk_free"
  fi
fi

if [[ "$health" == "OK" && "$gateway_overall" == "OK" && "$app_probe_failed" -eq 0 ]]; then
  printf 'NEXT:\n'
  printf -- '- No action needed.\n'
  exit 0
fi

printf -- '- health output: %s\n' "$(sed -n '1p' "$tmp" 2>/dev/null | tr -d '\r' || true)"
printf 'NEXT:\n'
if [[ "$app_probe_failed" -eq 1 ]]; then
  printf -- '- Check the Codex app-server listener and verify /readyz + /healthz on %s.\n' "$app_server_base"
elif [[ "$gateway_overall" == "DEGRADED" ]]; then
  printf -- '- Gateway is up but degraded; run openclaw gateway status --json, openclaw agents bindings --json, and openclaw plugins list --json.\n'
else
  printf -- '- Run scripts/diagnose_gateway.sh, then consider: openclaw gateway restart\n'
fi
exit 1
