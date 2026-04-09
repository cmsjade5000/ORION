#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

/usr/bin/python3 scripts/kalshi_autotrade_cycle.py
/usr/bin/python3 scripts/kalshi_cycle_freshness_check.py --repo-root "${repo_root}" --max-age-sec 600
