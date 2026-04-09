#!/usr/bin/env bash
set -euo pipefail

job="${1:-}"
if [[ -z "${job}" ]]; then
  echo "usage: $0 <job>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/Users/corystoner/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

freshness_check_single() {
  local pattern="$1"
  local max_age="$2"
  python3 - "$pattern" "$max_age" <<'PY'
import glob, os, sys, time
pattern = sys.argv[1]
max_age = int(sys.argv[2])
files = sorted(glob.glob(pattern))
if not files:
    raise SystemExit(2)
latest = max(files, key=os.path.getmtime)
age = time.time() - os.path.getmtime(latest)
print(latest)
print(int(age))
raise SystemExit(0 if age <= max_age else 3)
PY
}

freshness_check_pair() {
  local json_pattern="$1"
  local md_pattern="$2"
  local max_age="$3"
  python3 - "$json_pattern" "$md_pattern" "$max_age" <<'PY'
import glob, os, sys, time
json_pattern, md_pattern, max_age = sys.argv[1], sys.argv[2], int(sys.argv[3])
json_files = sorted(glob.glob(json_pattern))
md_files = sorted(glob.glob(md_pattern))
if not json_files or not md_files:
    raise SystemExit(2)
latest_json = max(json_files, key=os.path.getmtime)
latest_md = max(md_files, key=os.path.getmtime)
age = max(time.time() - os.path.getmtime(latest_json), time.time() - os.path.getmtime(latest_md))
print(latest_json)
print(latest_md)
print(int(age))
raise SystemExit(0 if age <= max_age else 3)
PY
}

case "${job}" in
  assistant-inbox-notify)
    exec /usr/bin/python3 scripts/notify_inbox_results.py --repo-root "${repo_root}" --require-notify-telegram --notify-queued --max-per-run 8
    ;;
  assistant-task-loop)
    exec /usr/bin/python3 scripts/task_execution_loop.py --apply --stale-hours 24
    ;;
  assistant-agenda-refresh)
    exec /usr/bin/python3 scripts/assistant_status.py --cmd refresh --json
    ;;
  orion-error-review)
    exec /usr/bin/python3 scripts/orion_error_db.py --repo-root . review --window-hours 24 --apply-safe-fixes --escalate-incidents --json
    ;;
  orion-session-maintenance)
    exec /usr/bin/env AUTO_OK=1 /usr/bin/python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json
    ;;
  orion-ops-bundle)
    exec /usr/bin/python3 scripts/openclaw_operator_health_bundle.py --repo-root . --agent main --output-md tasks/NOTES/operator-health-bundle.md --output-json tmp/operator-health-bundle.json
    ;;
  orion-judgment-layer)
    exec /usr/bin/python3 scripts/orion_judgment_layer.py --repo-root . --write-latest --json
    ;;
  kalshi-ref-arb-digest)
    exec /usr/bin/python3 -m scripts.kalshi_digest --window-hours 8 --send-email --email-html
    ;;
  kalshi-digest-delivery-guard)
    exec /usr/bin/python3 scripts/kalshi_digest_reliability.py --guard --send-telegram --grace-minutes 10
    ;;
  kalshi-digest-reliability-daily)
    exec /usr/bin/python3 scripts/kalshi_digest_reliability.py --daily-report --send-telegram
    ;;
  orion-reliability-daily)
    make eval-reliability-daily
    ;;
  orion-route-hygiene-daily)
    make route-hygiene
    freshness_check_single 'eval/history/route-hygiene-*.json' 900
    ;;
  orion-lane-hotspots-daily)
    make lane-hotspots HOURS=24 TOP=10
    freshness_check_single 'eval/history/lane-hotspots-*.json' 900
    ;;
  orion-stop-gate-daily)
    make stop-gate-enforce MIN_FAIL_DAYS=2
    freshness_check_pair 'eval/history/stop-gate-*.json' 'eval/history/stop-gate-*.md' 900
    ;;
  orion-monthly-scorecard-daily)
    export MONTH
    MONTH="$(date +%Y-%m)"
    make monthly-scorecard MONTH="${MONTH}"
    python3 - "$MONTH" <<'PY'
import os, sys, time
month = sys.argv[1]
path = f"eval/monthly-scorecard-{month}.md"
if not os.path.exists(path):
    raise SystemExit(2)
age = time.time() - os.path.getmtime(path)
print(int(age))
raise SystemExit(0 if age <= 1800 else 3)
PY
    ;;
  orion-skill-discovery-weekly)
    make skill-discovery LIMIT=8
    freshness_check_single 'eval/history/skills-discovery-*.json' 1800
    ;;
  orion-judgment-layer-freshness)
    freshness_check_pair 'eval/history/orion-judgment-*.json' 'eval/history/orion-judgment-*.md' 1800
    ;;
  *)
    echo "unknown job: ${job}" >&2
    exit 2
    ;;
esac
