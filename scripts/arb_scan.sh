#!/usr/bin/env bash
set -euo pipefail

# Read-only Polymarket arb scanner wrapper.
# Safe for inbox runner allowlist (no secrets, no writes).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT_DIR/scripts/arb_bot.py" scan "$@"

