#!/usr/bin/env bash
set -euo pipefail

# Install bounded-proactive assistant crons after Telegram inbound has been verified.
# Safe default: print commands unless --apply is passed.

APPLY=0
if [[ "${2:-}" == "--apply" || "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw is required" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 2
fi

legacy_names=(
  "assistant-agenda-refresh"
  "assistant-email-triage"
  "assistant-inbox-notify"
  "assistant-task-loop"
  "inbox-result-notify"
  "inbox-result-notify-discord"
  "task-loop-heartbeat"
  "task-loop-weekly-reconcile"
  "orion-error-review"
  "orion-session-maintenance"
  "orion-ops-bundle"
)

canonical_names=(
  "assistant-agenda-refresh"
  "assistant-email-triage"
  "assistant-inbox-notify"
  "orion-error-review"
  "orion-session-maintenance"
  "orion-ops-bundle"
)

run_cmd() {
  if [[ "$APPLY" -eq 1 ]]; then
    "$@"
  else
    printf '%q' "$1"
    shift
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n\n'
  fi
}

find_job_matches() {
  local jobs_json="$1"
  local job_name="$2"

  jq -c --arg name "$job_name" '
    [
      .jobs[]
      | select(.name == $name)
    ]
    | sort_by((.updatedAtMs // .createdAtMs // 0))
    | reverse
  ' <<<"$jobs_json"
}

remove_job_ids() {
  local ids_json="$1"

  jq -r '.[]' <<<"$ids_json" | while IFS= read -r job_id; do
    [[ -z "${job_id}" ]] && continue
    run_cmd openclaw cron rm --json "$job_id"
  done
}

prune_jobs() {
  local jobs_json="$1"
  local name matches ids_to_remove

  for name in "${canonical_names[@]}"; do
    matches="$(find_job_matches "$jobs_json" "$name")"
    ids_to_remove="$(
      jq '
        [
          .[]
          | select(
              (.sessionTarget // "") != "isolated"
              or ((.delivery.mode // "") != "none")
            )
          | .id
        ]
      ' <<<"$matches"
    )"
    remove_job_ids "$ids_to_remove"
    matches="$(find_job_matches "$jobs_json" "$name")"
    ids_to_remove="$(jq '[.[1:][]?.id]' <<<"$matches")"
    remove_job_ids "$ids_to_remove"
  done

  for name in "${legacy_names[@]}"; do
    case " ${canonical_names[*]} " in
      *" ${name} "*) continue ;;
    esac
    matches="$(find_job_matches "$jobs_json" "$name")"
    ids_to_remove="$(jq '[.[].id]' <<<"$matches")"
    remove_job_ids "$ids_to_remove"
  done
}

upsert_job() {
  local jobs_json="$1"
  local job_name="$2"
  local description="$3"
  local cron_expr="$4"
  local message="$5"
  local matches match_count job_id

  matches="$(find_job_matches "$jobs_json" "$job_name")"
  match_count="$(jq 'length' <<<"$matches")"

  if ((match_count == 0)); then
    run_cmd openclaw cron add \
      --name "$job_name" \
      --description "$description" \
      --cron "$cron_expr" \
      --tz "America/New_York" \
      --no-deliver \
      --agent main \
      --session isolated \
      --wake next-heartbeat \
      --message "$message"
    return
  fi

  job_id="$(jq -r '.[0].id' <<<"$matches")"
  run_cmd openclaw cron edit "$job_id" \
    --name "$job_name" \
    --description "$description" \
    --cron "$cron_expr" \
    --tz "America/New_York" \
    --enable \
    --no-deliver \
    --agent main \
    --session isolated \
    --wake next-heartbeat \
    --message "$message"
}

CMD1="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: python3 scripts/assistant_status.py --cmd refresh --json. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
CMD2="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: python3 scripts/email_triage_router.py --from-inbox orion_gatewaybot@agentmail.to --limit 20 --apply. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
CMD3="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: python3 scripts/inbox_cycle.py --repo-root . --runner-max-packets 4 --stale-hours 24 --notify-max-per-run 8. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
CMD4="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: python3 scripts/orion_error_db.py --repo-root . review --window-hours 24 --apply-safe-fixes --escalate-incidents --json. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
CMD5="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
CMD6="Use system.run exactly once, without elevated mode and without a TTY, to execute exactly: python3 scripts/orion_incident_bundle.py --repo-root . --write-latest --json. Do not request elevated execution. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."

jobs_json="$(openclaw cron list --all --json)"
prune_jobs "$jobs_json"
jobs_json="$(openclaw cron list --all --json)"

upsert_job "$jobs_json" "assistant-agenda-refresh" "Refresh ORION assistant agenda artifact" "*/15 * * * *" "$CMD1"
upsert_job "$jobs_json" "assistant-email-triage" "Poll ORION AgentMail and route safe inbound email into inbox task packets" "*/5 * * * *" "$CMD2"
upsert_job "$jobs_json" "assistant-inbox-notify" "Advance safe inbox work, reconcile lanes, and notify Cory" "*/2 * * * *" "$CMD3"
upsert_job "$jobs_json" "orion-error-review" "Review recurring ORION errors and apply safe remediations" "15 2 * * *" "$CMD4"
upsert_job "$jobs_json" "orion-session-maintenance" "Prune stale ORION session metadata when drift exceeds threshold" "45 2 * * *" "$CMD5"
upsert_job "$jobs_json" "orion-ops-bundle" "Capture a read-only ORION incident bundle with gateway, flow, and Codex posture evidence" "30 3 * * *" "$CMD6"
