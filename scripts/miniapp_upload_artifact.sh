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

if [[ -n "${INGEST_TOKEN:-}" && -n "${AGENT_ID}" ]]; then
  curl -sS -X POST "${BASE_URL%/}/api/artifacts" \
    -H "Authorization: Bearer ${INGEST_TOKEN}" \
    -H "x-agent-id: ${AGENT_ID}" \
    -H "Content-Type: ${MIME}" \
    -H "x-artifact-name: ${NAME}" \
    --data-binary @"${FILE_PATH}"
elif [[ -n "${INGEST_TOKEN:-}" ]]; then
  curl -sS -X POST "${BASE_URL%/}/api/artifacts" \
    -H "Authorization: Bearer ${INGEST_TOKEN}" \
    -H "Content-Type: ${MIME}" \
    -H "x-artifact-name: ${NAME}" \
    --data-binary @"${FILE_PATH}"
elif [[ -n "${AGENT_ID}" ]]; then
  curl -sS -X POST "${BASE_URL%/}/api/artifacts" \
    -H "x-agent-id: ${AGENT_ID}" \
    -H "Content-Type: ${MIME}" \
    -H "x-artifact-name: ${NAME}" \
    --data-binary @"${FILE_PATH}"
else
  curl -sS -X POST "${BASE_URL%/}/api/artifacts" \
    -H "Content-Type: ${MIME}" \
    -H "x-artifact-name: ${NAME}" \
    --data-binary @"${FILE_PATH}"
fi

echo
