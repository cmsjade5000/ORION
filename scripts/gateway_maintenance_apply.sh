#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Apply daily maintenance on the ORION host (Cory runs; safe by default).
# This is intentionally explicit and gated; do not run unattended unless you
# have explicitly enabled that posture.

AUTO_OK="${AUTO_OK:-0}"
DO_FIX="${DO_FIX:-0}"
DO_UPDATE="${DO_UPDATE:-0}"
DO_REPAIR="${DO_REPAIR:-0}"
DO_COMMIT="${DO_COMMIT:-0}"
DO_PUSH="${DO_PUSH:-0}"
DO_RESTART="${DO_RESTART:-0}"
DO_SESSIONS="${DO_SESSIONS:-0}"

usage() {
  cat <<'TXT' >&2
Usage:
  scripts/gateway_maintenance_apply.sh [options]

Default behavior is CHECK-ONLY (no changes). Destructive options require AUTO_OK=1.

Options:
  --fix        Run: openclaw security audit --deep --fix
  --update     Run: openclaw update --yes
  --repair     Run: openclaw doctor --repair --non-interactive
  --sessions   Run: scripts/sessions_hygiene.sh --apply --fix-missing
  --commit     Commit any repo changes (after secrets scan)
  --push       Push to origin (implies --commit)
  --restart    Restart OpenClaw gateway service (openclaw gateway restart)
  -h, --help   Show this help

Env:
  AUTO_OK=1    Required to run any of: --fix/--update/--repair/--sessions/--commit/--push/--restart
TXT
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix) DO_FIX=1; shift ;;
    --update) DO_UPDATE=1; shift ;;
    --repair) DO_REPAIR=1; shift ;;
    --sessions) DO_SESSIONS=1; shift ;;
    --commit) DO_COMMIT=1; shift ;;
    --push) DO_PUSH=1; DO_COMMIT=1; shift ;;
    --restart) DO_RESTART=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

need_auto_ok=$((DO_FIX + DO_UPDATE + DO_REPAIR + DO_SESSIONS + DO_COMMIT + DO_PUSH + DO_RESTART))
if [[ "$need_auto_ok" -gt 0 ]] && [[ "$AUTO_OK" != "1" ]]; then
  echo "ERROR: Refusing to apply changes without AUTO_OK=1" >&2
  exit 2
fi

ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
day="$(date -u '+%Y-%m-%d')"

echo "MAINT_START ts=$ts"

echo "1) Security audit (deep)"
openclaw security audit --deep --json | jq -r '.summary' || true

echo "2) Update status"
if openclaw update status >/dev/null 2>&1; then
  openclaw update status || true
else
  openclaw update --json status || true
fi

echo "3) Session hygiene dry-run"
"${repo_root}/scripts/sessions_hygiene.sh" --agent main --fix-missing || true

if [[ "$DO_FIX" = "1" ]]; then
  echo "4) Apply safe security fixes"
  openclaw security audit --deep --fix || true
fi

if [[ "$DO_REPAIR" = "1" ]]; then
  echo "5) Doctor repair (non-interactive)"
  openclaw doctor --repair --non-interactive || true
fi

if [[ "$DO_UPDATE" = "1" ]]; then
  echo "6) OpenClaw update (non-interactive)"
  openclaw update --yes || true
fi

if [[ "$DO_SESSIONS" = "1" ]]; then
  echo "7) Session hygiene maintenance"
  AUTO_OK=1 "${repo_root}/scripts/sessions_hygiene.sh" --agent main --fix-missing --doctor --apply || true
fi

if [[ "$DO_COMMIT" = "1" ]]; then
  echo "8) Secrets scan (fast rg pattern scan)"
  rg -n -S -P "(sk-or-v1-[A-Za-z0-9]{20,}|AIzaSy[A-Za-z0-9_-]{20,}|xoxb-[A-Za-z0-9-]{10,}|xapp-[A-Za-z0-9-]{10,}|mm_live_[A-Za-z0-9]+|\\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\\b)" . && {
    echo "ERROR: Potential secret match detected. Refusing to commit." >&2
    exit 2
  } || true

  if [[ -n "$(git status --porcelain=v1)" ]]; then
    echo "9) CI gate"
    make ci

    echo "10) Commit"
    git add -A
    git commit -m "chore(maintenance): daily gateway maintenance (${day})"

    if [[ "$DO_PUSH" = "1" ]]; then
      echo "11) Push"
      git push
    fi
  else
    echo "9) No repo changes; skipping commit/push"
  fi
fi

if [[ "$DO_RESTART" = "1" ]]; then
  echo "12) Restart gateway"
  openclaw gateway restart
fi

echo "MAINT_OK ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
