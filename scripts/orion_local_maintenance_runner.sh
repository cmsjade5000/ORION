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
    exec /usr/bin/python3 scripts/inbox_cycle.py --repo-root "${repo_root}" --runner-max-packets 4 --stale-hours 24 --notify-max-per-run 8
    ;;
  assistant-email-triage)
    exec /usr/bin/python3 scripts/email_triage_router.py --from-inbox orion_gatewaybot@agentmail.to --limit 20 --apply
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
  orion-yeet-worktree)
    exec /usr/bin/env /bin/bash scripts/orion_yeet_worktree.sh
    ;;
  *)
    echo "unknown job: ${job}" >&2
    exit 2
    ;;
esac
