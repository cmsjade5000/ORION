#!/usr/bin/env bash
set -euo pipefail

# NODE: basic gateway/node tooling checks (read-only).

hr() { printf '\n== %s ==\n' "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW="$ROOT/scripts/openclaww.sh"

hr "Gateway Health"
"$OPENCLAW" health || true

hr "Gateway Status"
"$OPENCLAW" gateway status || true

hr "Cron Scheduler Status"
"$OPENCLAW" cron status || true

