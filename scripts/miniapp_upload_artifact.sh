#!/usr/bin/env bash
set -euo pipefail

# Upload a file to the Telegram mini app dashboard so it appears as a floating
# "artifact bubble" the user can tap to download.
#
# Env:
#   INGEST_TOKEN   Optional. If set, sent as Authorization Bearer token.
#
# Usage:
#   ./scripts/miniapp_upload_artifact.sh <miniapp_base_url> <file_path> [download_name] [mime] [agent_id]
#
# Examples:
#   INGEST_TOKEN=... ./scripts/miniapp_upload_artifact.sh https://<app>.fly.dev ./out/xyz.pdf xyz.pdf application/pdf LEDGER

BASE_URL="${1:-}"
FILE_PATH="${2:-}"
NAME="${3:-}"
MIME="${4:-}"
AGENT_ID="${5:-}"

if [[ -z "${BASE_URL}" || -z "${FILE_PATH}" ]]; then
  echo "Usage: $0 <miniapp_base_url> <file_path> [download_name] [mime] [agent_id]" >&2
  exit 2
fi

if [[ ! -f "${FILE_PATH}" ]]; then
  echo "File not found: ${FILE_PATH}" >&2
  exit 2
fi

if [[ -z "${NAME}" ]]; then
  NAME="$(basename "${FILE_PATH}")"
fi

if [[ -z "${MIME}" ]]; then
  # Best-effort MIME inference (macOS `file` is commonly present).
  if command -v file >/dev/null 2>&1; then
    MIME="$(file -b --mime-type "${FILE_PATH}" 2>/dev/null || true)"
  fi
  MIME="${MIME:-application/octet-stream}"
fi

token_transport_allowed() {
  case "$1" in
    https://*|http://localhost|http://localhost/*|http://localhost:*|http://127.0.0.1|http://127.0.0.1/*|http://127.0.0.1:*|http://[::1]|http://[::1]/*|http://[::1]:*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Fallback: if INGEST_TOKEN is not present in the current shell, try loading it
# from OpenClaw config so agent-executed shell commands can still upload.
if [[ -z "${INGEST_TOKEN:-}" ]]; then
  CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
  if [[ -f "${CFG}" ]] && command -v python3 >/dev/null 2>&1; then
    INGEST_TOKEN="$(
      python3 - "${CFG}" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
try:
    obj = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
vars_obj = ((obj.get("env") or {}).get("vars") or {})
tok = vars_obj.get("MINIAPP_INGEST_TOKEN") or vars_obj.get("INGEST_TOKEN") or ""
print(str(tok).strip())
PY
    )"
    export INGEST_TOKEN
  fi
fi

if [[ -n "${INGEST_TOKEN:-}" ]] && ! token_transport_allowed "${BASE_URL}"; then
  echo "Refusing token-auth upload over non-HTTPS transport (HTTP allowed only for localhost)." >&2
  exit 2
fi

upload_url="${BASE_URL%/}/api/artifacts"
response_file="$(mktemp -t miniapp-upload-response.XXXXXX)"
trap 'rm -f "${response_file}"' EXIT

curl_args=(
  -sS
  -o "${response_file}"
  -w "%{http_code}"
  -X POST "${upload_url}"
  -H "Content-Type: ${MIME}"
  -H "x-artifact-name: ${NAME}"
  --data-binary @"${FILE_PATH}"
)

if [[ -n "${INGEST_TOKEN:-}" ]]; then
  curl_args+=(-H "Authorization: Bearer ${INGEST_TOKEN}")
fi
if [[ -n "${AGENT_ID}" ]]; then
  curl_args+=(-H "x-agent-id: ${AGENT_ID}")
fi

http_code="$(curl "${curl_args[@]}")" || {
  echo "Upload request failed." >&2
  if [[ -s "${response_file}" ]]; then
    cat "${response_file}" >&2
    echo >&2
  fi
  exit 1
}

if [[ ! "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
  echo "Upload failed with HTTP ${http_code}." >&2
  if [[ -s "${response_file}" ]]; then
    cat "${response_file}" >&2
    echo >&2
  fi
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  if ! python3 - "${response_file}" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
try:
    obj = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)
if not isinstance(obj, dict) or obj.get("ok") is not True:
    raise SystemExit(1)
PY
  then
    echo "Upload response did not indicate success (expected JSON with ok=true)." >&2
    cat "${response_file}" >&2 || true
    echo >&2
    exit 1
  fi
else
  if ! grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' "${response_file}"; then
    echo "Upload response did not indicate success (expected ok=true)." >&2
    cat "${response_file}" >&2 || true
    echo >&2
    exit 1
  fi
fi

cat "${response_file}"
echo
