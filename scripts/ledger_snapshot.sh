#!/usr/bin/env bash
set -euo pipefail

# LEDGER: record a quick repo status snapshot (read-only).

hr() { printf '\n== %s ==\n' "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

hr "Git Branch"
git branch --show-current || true

hr "Git Status"
git status --porcelain || true

hr "Last Commit"
git log -1 --oneline --decorate || true

