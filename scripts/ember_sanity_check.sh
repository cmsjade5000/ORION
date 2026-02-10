#!/usr/bin/env bash
set -euo pipefail

# EMBER: local orchestration sanity checks (read-only).

hr() { printf '\n== %s ==\n' "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

hr "OpenClaw Health"
"$ROOT/scripts/openclaww.sh" health || true

hr "LaunchAgents (Relevant)"
UID_NUM="$(id -u)"
for label in \
  "ai.orion.inbox_packet_runner" \
  "ai.orion.inbox_result_notify"
do
  printf '\n-- %s --\n' "$label"
  launchctl print "gui/$UID_NUM/$label" 2>/dev/null | sed -n '1,35p' || echo "not_loaded"
done
