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

AUTH_HEADER=()
if [[ -n "${INGEST_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${INGEST_TOKEN}")
fi

AGENT_HEADER=()
if [[ -n "${AGENT_ID}" ]]; then
  AGENT_HEADER=(-H "x-agent-id: ${AGENT_ID}")
fi

curl -sS -X POST "${BASE_URL%/}/api/artifacts" \
  "${AUTH_HEADER[@]}" \
  "${AGENT_HEADER[@]}" \
  -H "Content-Type: ${MIME}" \
  -H "x-artifact-name: ${NAME}" \
  --data-binary @"${FILE_PATH}"

echo

