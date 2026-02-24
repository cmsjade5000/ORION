#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cfg="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

url="${MINIAPP_COMMAND_RELAY_URL:-}"
tok="${MINIAPP_COMMAND_RELAY_TOKEN:-}"

json_get() {
  local file="$1"
  local path="$2"
  /usr/bin/python3 - "$file" "$path" <<'PY'
import json, sys
fp = sys.argv[1]
path = sys.argv[2].split(".")
try:
    with open(fp, "r", encoding="utf-8") as f:
        obj = json.load(f)
    cur = obj
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            print("")
            raise SystemExit(0)
        cur = cur[p]
    print(cur if isinstance(cur, str) else "")
except Exception:
    print("")
PY
}

if [[ -z "${url}" && -f "${cfg}" ]]; then
  url="$(json_get "${cfg}" "env.vars.MINIAPP_INGEST_URL")"
  if [[ -z "${url}" ]]; then
    url="$(json_get "${cfg}" "env.vars.ORION_MINIAPP_URL")"
  fi
fi
if [[ -z "${tok}" && -f "${cfg}" ]]; then
  tok="$(json_get "${cfg}" "env.vars.MINIAPP_INGEST_TOKEN")"
  if [[ -z "${tok}" ]]; then
    tok="$(json_get "${cfg}" "env.vars.INGEST_TOKEN")"
  fi
fi

if [[ -z "${url}" || -z "${tok}" ]]; then
  echo "miniapp relay missing URL/token; set MINIAPP_COMMAND_RELAY_URL and MINIAPP_COMMAND_RELAY_TOKEN or configure ~/.openclaw/openclaw.json env.vars."
  exit 2
fi

export MINIAPP_COMMAND_RELAY_URL="${url}"
export MINIAPP_COMMAND_RELAY_TOKEN="${tok}"

py=""
for cand in "/opt/homebrew/bin/python3" "/usr/local/bin/python3" "$(command -v python3 2>/dev/null || true)" "/usr/bin/python3"; do
  if [[ -n "${cand}" && -x "${cand}" ]]; then
    py="${cand}"
    break
  fi
done
if [[ -z "${py}" ]]; then
  echo "miniapp relay missing python3 runtime"
  exit 2
fi

exec "${py}" "${repo_root}/scripts/miniapp_command_relay.py"
