#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export ORION_WORKSPACE="${ORION_WORKSPACE:-$repo_root}"
export ORION_MINIAPP_HOST="${ORION_MINIAPP_HOST:-0.0.0.0}"
export ORION_MINIAPP_PORT="${ORION_MINIAPP_PORT:-8787}"

exec /opt/homebrew/bin/node apps/extensions/telegram/orion-miniapp/server.cjs
