#!/usr/bin/env bash
set -euo pipefail

# Poll Hetzner AEGIS for newly-created defense plans and DM Cory from the ORION bot.
#
# Intended to run periodically (launchd), once per invocation.
#
# Env:
#   AEGIS_HOST (default 100.75.104.54)
#   AEGIS_SSH_USER (default root)
#   ORION_TELEGRAM_CHAT_ID (preferred). If unset, falls back to AEGIS_TELEGRAM_CHAT_ID from /etc/aegis-monitor.env on Hetzner.
#   STATE_FILE (default: <repo>/tmp/aegis_defense_plans.seen)
#   DRY_RUN=1 (do not send; just print what would happen)
#
# Uses:
#   scripts/aegis_defense.sh list
#   scripts/telegram_send_message.sh

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# run_with_timeout: run a command with a hard timeout to prevent hangs.
# Usage: run_with_timeout <seconds> <command> [args...]
run_with_timeout() {
  local timeout_sec="${1:-30}"
  shift
  local cmd=("$@")
  
  # Run the command in background
  "${cmd[@]}" &
  local cmd_pid=$!
  
  # Timer to kill after timeout
  (
    sleep "$timeout_sec"
    if kill -0 "$cmd_pid" 2>/dev/null; then
      echo "run_with_timeout: killing ${cmd[*]} after ${timeout_sec}s" >&2
      kill -TERM "$cmd_pid" 2>/dev/null || kill -KILL "$cmd_pid" 2>/dev/null
    fi
  ) &
  local timer_pid=$!
  
  # Wait for command to finish
  wait "$cmd_pid" 2>/dev/null
  local exit_code=$?
  
  # Cleanup timer
  kill -TERM "$timer_pid" 2>/dev/null || true
  wait "$timer_pid" 2>/dev/null || true
  
  return $exit_code
}

AEGIS_HOST="${AEGIS_HOST:-100.75.104.54}"
AEGIS_SSH_USER="${AEGIS_SSH_USER:-root}"
AEGIS_SSH_STRICT_HOST_KEY_CHECKING="${AEGIS_SSH_STRICT_HOST_KEY_CHECKING:-yes}"
AEGIS_SSH_KNOWN_HOSTS="${AEGIS_SSH_KNOWN_HOSTS:-${HOME}/.ssh/known_hosts}"
STATE_FILE="${STATE_FILE:-${repo_root}/tmp/aegis_defense_plans.seen}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "${repo_root}/tmp"
touch "${STATE_FILE}"

get_chat_id() {
  if [[ -n "${ORION_TELEGRAM_CHAT_ID:-}" ]]; then
    echo "${ORION_TELEGRAM_CHAT_ID}"
    return 0
  fi

  # Best-effort fallback: use whatever chat id AEGIS is configured to alert.
  # (This is often Cory's DM chat_id.)
  local line val
  # Use run_with_timeout to prevent SSH hangs; on error/timeout, treat as no output.
  line="$(run_with_timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=5 \
    -o "StrictHostKeyChecking=${AEGIS_SSH_STRICT_HOST_KEY_CHECKING}" \
    -o "UserKnownHostsFile=${AEGIS_SSH_KNOWN_HOSTS}" \
    "${AEGIS_SSH_USER}@${AEGIS_HOST}" \
    "grep -E '^AEGIS_TELEGRAM_CHAT_ID=' /etc/aegis-monitor.env 2>/dev/null | tail -n 1" || true)"
  val="${line#*=}"
  val="${val%\"}"
  val="${val#\"}"
  echo "${val}"
}

chat_id="$(get_chat_id)"
if [[ -z "${chat_id}" ]]; then
  echo "aegis_defense_watch: missing chat id (set ORION_TELEGRAM_CHAT_ID)" >&2
  exit 0
fi

# Fetch plans with a timeout to prevent SSH hang
plans="$(run_with_timeout 30 "${repo_root}/scripts/aegis_defense.sh" list 2>/dev/null || true)"
if [[ -z "${plans}" ]]; then
  exit 0
fi

seen="$(cat "${STATE_FILE}" 2>/dev/null || true)"

new_ids=()
while IFS= read -r id; do
  [[ -z "${id}" ]] && continue
  if ! printf '%s\n' "${seen}" | grep -qxF "${id}"; then
    new_ids+=("${id}")
  fi
done <<< "${plans}"

if [[ "${#new_ids[@]}" -eq 0 ]]; then
  exit 0
fi

# Record first, then notify (avoid double-sends if the send fails mid-run).
{
  cat "${STATE_FILE}"
  printf '%s\n' "${new_ids[@]}"
} | awk 'NF' | sort -u > "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "${STATE_FILE}"

for id in "${new_ids[@]}"; do
  kind="Plan"
  if [[ "${id}" == INC-AEGIS-MAINT-* ]]; then
    kind="Maintenance Plan"
  elif [[ "${id}" == INC-AEGIS-SEC-* ]]; then
    kind="Defense Plan"
  fi
  msg=$(
    cat <<EOF
AEGIS prepared a ${kind}: ${id}

Reply "review ${id}" and I will walk you through it, or run:
scripts/aegis_defense.sh show ${id}
EOF
  )
  if [[ "${DRY_RUN}" = "1" ]]; then
    echo "DRY_RUN: would DM chat_id=${chat_id} incident=${id}"
    continue
  fi
  "${repo_root}/scripts/telegram_send_message.sh" "${chat_id}" "${msg}"
done
