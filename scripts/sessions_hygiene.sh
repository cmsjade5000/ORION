#!/usr/bin/env bash
set -euo pipefail

# Safe session-store maintenance for a single agent.
# Default: dry-run only. Use --apply with AUTO_OK=1 to mutate state.

AUTO_OK="${AUTO_OK:-0}"
AGENT_ID="main"
APPLY=0
FIX_MISSING=0
RUN_DOCTOR=0

usage() {
  cat <<'TXT' >&2
Usage:
  scripts/sessions_hygiene.sh [options]

Default mode is dry-run (no changes).

Options:
  --agent <id>     Agent id to maintain (default: main)
  --apply          Apply maintenance (requires AUTO_OK=1)
  --fix-missing    Include pruning of entries whose transcript files are missing
  --doctor         Run openclaw doctor after cleanup
  -h, --help       Show this help

Env:
  AUTO_OK=1        Required with --apply
TXT
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT_ID="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --fix-missing) FIX_MISSING=1; shift ;;
    --doctor) RUN_DOCTOR=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ "$APPLY" = "1" ]] && [[ "$AUTO_OK" != "1" ]]; then
  echo "ERROR: Refusing to apply session hygiene without AUTO_OK=1" >&2
  exit 2
fi

ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "SESSIONS_HYGIENE_START ts=${ts} agent=${AGENT_ID} apply=${APPLY} fix_missing=${FIX_MISSING}"

args=(--agent "$AGENT_ID")
if [[ "$FIX_MISSING" = "1" ]]; then
  args+=(--fix-missing)
fi

echo "1) Dry-run preview"
preview_json="$(openclaw sessions cleanup "${args[@]}" --dry-run --json)"
echo "$preview_json"

if command -v jq >/dev/null 2>&1; then
  before_count="$(jq -r '.beforeCount // "n/a"' <<<"$preview_json")"
  after_count="$(jq -r '.afterCount // "n/a"' <<<"$preview_json")"
  missing_count="$(jq -r '.missing // "n/a"' <<<"$preview_json")"
  mutate_flag="$(jq -r '.wouldMutate // "n/a"' <<<"$preview_json")"
  echo "Preview summary: entries ${before_count} -> ${after_count}, missing=${missing_count}, wouldMutate=${mutate_flag}"
fi

if [[ "$APPLY" = "1" ]]; then
  echo "2) Apply cleanup"
  openclaw sessions cleanup "${args[@]}" --enforce --json
fi

if [[ "$RUN_DOCTOR" = "1" ]]; then
  echo "3) Doctor state check"
  openclaw doctor --non-interactive
fi

echo "SESSIONS_HYGIENE_OK ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
