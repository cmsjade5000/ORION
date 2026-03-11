#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Telegram topic -> agent routing entries in runtime config.
# Default mode is dry-run; use --apply to write settings.

APPLY=0
GROUP_ID=""
declare -a TOPIC_MAPS=()

usage() {
  cat <<'TXT' >&2
Usage:
  scripts/telegram_topic_bindings_bootstrap.sh --group-id <chat_id> --topic <topic_id:agent_id> [--topic ...] [options]

Options:
  --group-id <id>         Telegram group chat id (e.g. -1001234567890)
  --topic <id:agent>      Map one topic id to one agent id (repeatable)
  --apply                 Apply config and bindings (default: dry-run)
  -h, --help              Show this help

Examples:
  scripts/telegram_topic_bindings_bootstrap.sh \
    --group-id -1001234567890 \
    --topic 1:main \
    --topic 42:atlas

  scripts/telegram_topic_bindings_bootstrap.sh \
    --group-id -1001234567890 \
    --topic 7:ledger \
    --apply
TXT
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --group-id) GROUP_ID="${2:-}"; shift 2 ;;
    --topic) TOPIC_MAPS+=("${2:-}"); shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "$GROUP_ID" ]] || [[ "${#TOPIC_MAPS[@]}" -eq 0 ]]; then
  usage
fi

echo "TELEGRAM_TOPIC_BOOTSTRAP group=${GROUP_ID} apply=${APPLY}"

for entry in "${TOPIC_MAPS[@]}"; do
  topic_id="${entry%%:*}"
  agent_id="${entry#*:}"

  if [[ -z "$topic_id" ]] || [[ -z "$agent_id" ]] || [[ "$topic_id" = "$entry" ]]; then
    echo "Invalid --topic value: ${entry}. Expected <topic_id:agent_id>." >&2
    exit 2
  fi

  # Use bracket-notation for negative chat IDs and quote topic keys.
  config_path="channels.telegram.groups[\"${GROUP_ID}\"].topics[\"${topic_id}\"].agentId"
  bind_value="telegram:${GROUP_ID}:topic:${topic_id}"

  if [[ "$APPLY" = "1" ]]; then
    echo "Applying topic mapping: group=${GROUP_ID} topic=${topic_id} -> agent=${agent_id}"
    openclaw config set "${config_path}" "${agent_id}"
    echo "Ensuring topic-scoped routing binding for agent=${agent_id}: ${bind_value}"
    openclaw agents bind --agent "${agent_id}" --bind "${bind_value}" --json
  else
    echo "DRY-RUN topic mapping: openclaw config set '${config_path}' '${agent_id}'"
    echo "DRY-RUN binding: openclaw agents bind --agent '${agent_id}' --bind '${bind_value}' --json"
  fi
done

if [[ "$APPLY" = "1" ]]; then
  openclaw config validate --json
fi

echo "TELEGRAM_TOPIC_BOOTSTRAP_OK"
