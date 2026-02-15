#!/usr/bin/env bash
set -euo pipefail

# Configure a high-autonomy Discord posture for ORION and print an invite URL
# with broad, non-admin permissions.
#
# Usage:
#   scripts/discord_autonomy_bootstrap.sh <discord_app_id> <guild_id> <primary_channel_id> [updates_channel_id]
#
# Example:
#   scripts/discord_autonomy_bootstrap.sh 123456789012345678 111111111111111111 222222222222222222 333333333333333333

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <discord_app_id> <guild_id> <primary_channel_id> [updates_channel_id]" >&2
  exit 2
fi

APP_ID="$1"
GUILD_ID="$2"
PRIMARY_CHANNEL_ID="$3"
UPDATES_CHANNEL_ID="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW="${OPENCLAW_BIN:-${SCRIPT_DIR}/openclaww.sh}"
if [[ ! -x "${OPENCLAW}" ]]; then
  OPENCLAW="openclaw"
fi

if ! command -v "${OPENCLAW}" >/dev/null 2>&1; then
  echo "openclaw not found. Set OPENCLAW_BIN or ensure scripts/openclaww.sh works." >&2
  exit 127
fi

# Broad autonomy permissions (non-admin):
# - View Channels, Send Messages, Embed Links, Attach Files, Add Reactions
# - Read Message History
# - Create/Manage Threads, Send Messages in Threads
# - Use Application Commands
# - Manage Messages, Use External Emojis
DISCORD_PERMISSIONS_INT="397284867136"
INVITE_URL="https://discord.com/api/oauth2/authorize?client_id=${APP_ID}&permissions=${DISCORD_PERMISSIONS_INT}&scope=bot%20applications.commands"

set_cfg() {
  "${OPENCLAW}" config set "$@"
}

echo "Applying high-autonomy Discord config for guild ${GUILD_ID}..."

set_cfg channels.discord.enabled true
set_cfg channels.discord.token "\${DISCORD_BOT_TOKEN}"
set_cfg channels.discord.allowBots false
set_cfg channels.discord.replyToMode off

# Keep DMs restricted while making guild operations autonomous.
set_cfg channels.discord.dm.policy allowlist
set_cfg channels.discord.groupPolicy allowlist
set_cfg channels.discord.guilds."${GUILD_ID}".requireMention false
set_cfg channels.discord.guilds."${GUILD_ID}".channels."${PRIMARY_CHANNEL_ID}".allow true
set_cfg channels.discord.guilds."${GUILD_ID}".channels."${PRIMARY_CHANNEL_ID}".autoThread true

if [[ -n "${UPDATES_CHANNEL_ID}" ]]; then
  set_cfg channels.discord.guilds."${GUILD_ID}".channels."${UPDATES_CHANNEL_ID}".allow true
  set_cfg channels.discord.guilds."${GUILD_ID}".channels."${UPDATES_CHANNEL_ID}".autoThread false
fi

echo
echo "High-autonomy config written."
echo "Invite ORION with broad non-admin permissions:"
echo "${INVITE_URL}"
echo
echo "Next checks:"
echo "  ${SCRIPT_DIR}/discord_selfcheck.sh"
echo "  ${OPENCLAW} channels status --probe --json"
