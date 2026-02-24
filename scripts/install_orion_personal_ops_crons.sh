#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

APPLY=0
TZ_VALUE="America/New_York"
MORNING_CRON="15 7 * * 1-5"
EVENING_CRON="30 20 * * 1-5"
DELIVERY_ARGS=(--no-deliver)

JOB_MORNING="orion-personal-morning-brief"
JOB_EVENING="orion-personal-evening-reset"

usage() {
  cat <<USAGE
Usage: ${SCRIPT_NAME} [options]

Install or update ORION personal ops cron jobs safely.
Defaults to dry-run; pass --apply to make changes.

Options:
  --apply                    Apply changes (default: dry-run)
  --tz <IANA>                Timezone (default: America/New_York)
  --morning-cron <expr>      Morning cron (default: "15 7 * * 1-5")
  --evening-cron <expr>      Evening cron (default: "30 20 * * 1-5")
  --announce                 Enable announce delivery (default: no-deliver)
  -h, --help                 Show this help
USAGE
}

err() {
  printf 'error: %s\n' "$*" >&2
}

validate_dependencies() {
  if [[ -z "${BASH_VERSION:-}" ]]; then
    err "bash runtime not detected"
    exit 1
  fi

  local dep
  for dep in bash openclaw jq; do
    if ! command -v "$dep" >/dev/null 2>&1; then
      err "required dependency not found: ${dep}"
      exit 1
    fi
  done
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --apply)
        APPLY=1
        shift
        ;;
      --tz)
        if (($# < 2)); then
          err "--tz requires a value"
          exit 1
        fi
        TZ_VALUE="$2"
        shift 2
        ;;
      --morning-cron)
        if (($# < 2)); then
          err "--morning-cron requires a value"
          exit 1
        fi
        MORNING_CRON="$2"
        shift 2
        ;;
      --evening-cron)
        if (($# < 2)); then
          err "--evening-cron requires a value"
          exit 1
        fi
        EVENING_CRON="$2"
        shift 2
        ;;
      --announce)
        DELIVERY_ARGS=(--announce)
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        err "unknown argument: $1"
        usage
        exit 1
        ;;
    esac
  done

  if [[ -z "$TZ_VALUE" ]]; then
    err "timezone must not be empty"
    exit 1
  fi
}

log_cmd() {
  local mode="dry-run"
  if ((APPLY)); then
    mode="apply"
  fi

  printf '%s:' "$mode"
  printf ' %q' "$@"
  printf '\n'
}

run_cmd() {
  log_cmd "$@"
  if ((APPLY)); then
    "$@"
  fi
}

morning_message() {
  cat <<'MSG'
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Build a concise MORNING BRIEF for Cory with clear priorities and the first 15-minute action.
Success Criteria:
- Produces a Morning Brief using the daily briefing template.
- Explicitly lists assumptions and missing inputs; no fabricated facts.
- Includes mission, top outcomes, schedule reality check, deadlines, and energy plan.
Constraints:
- Keep output concise and actionable.
- Do not claim reminder/scheduling changes are already configured.
- No destructive commands.
Inputs:
- skills/daily-briefing/SKILL.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any credential/configuration mutation.
Output Format:
- Daily briefing text only (morning format).
MSG
}

evening_message() {
  cat <<'MSG'
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Run an evening reset and produce the next life-admin queue for tomorrow.
Success Criteria:
- Produces an evening reset with carry-forward and tomorrow setup.
- Produces a prioritized life-admin today/next queue with blockers if present.
- Explicitly marks assumptions and missing inputs; no fabricated facts.
Constraints:
- Keep output concise and execution-focused.
- No irreversible actions.
- No destructive commands.
Inputs:
- skills/daily-briefing/SKILL.md
- skills/life-admin-queue/SKILL.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any irreversible financial/legal action.
Output Format:
- Evening reset summary plus life-admin queue sections.
MSG
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

upsert_job() {
  local jobs_json="$1"
  local job_name="$2"
  local cron_expr="$3"
  local message="$4"

  local matches
  local match_count
  local job_id

  matches="$(find_job_matches "$jobs_json" "$job_name")"
  match_count="$(jq 'length' <<<"$matches")"

  if ((match_count > 1)); then
    printf 'warn: found %s jobs named %s; updating most recently changed entry\n' "$match_count" "$job_name" >&2
  fi

  if ((match_count == 0)); then
    printf 'job: %s -> create\n' "$job_name"
    run_cmd openclaw cron add \
      --name "$job_name" \
      --agent main \
      --cron "$cron_expr" \
      --tz "$TZ_VALUE" \
      --session isolated \
      --wake next-heartbeat \
      "${DELIVERY_ARGS[@]}" \
      --message "$message"
    return
  fi

  job_id="$(jq -r '.[0].id' <<<"$matches")"
  printf 'job: %s -> edit+enable (%s)\n' "$job_name" "$job_id"
  run_cmd openclaw cron edit "$job_id" \
    --name "$job_name" \
    --agent main \
    --cron "$cron_expr" \
    --tz "$TZ_VALUE" \
    --session isolated \
    --wake next-heartbeat \
    --enable \
    "${DELIVERY_ARGS[@]}" \
    --message "$message"
}

main() {
  parse_args "$@"
  validate_dependencies

  local mode="DRY-RUN"
  if ((APPLY)); then
    mode="APPLY"
  fi

  local delivery_mode="no-deliver"
  if [[ "${DELIVERY_ARGS[*]}" == "--announce" ]]; then
    delivery_mode="announce"
  fi

  printf 'orion cron installer mode: %s\n' "$mode"
  printf 'timezone: %s\n' "$TZ_VALUE"
  printf 'delivery: %s\n' "$delivery_mode"

  local jobs_json
  jobs_json="$(openclaw cron list --all --json)"

  local morning_payload
  local evening_payload
  morning_payload="$(morning_message)"
  evening_payload="$(evening_message)"

  upsert_job "$jobs_json" "$JOB_MORNING" "$MORNING_CRON" "$morning_payload"
  upsert_job "$jobs_json" "$JOB_EVENING" "$EVENING_CRON" "$evening_payload"

  if ((APPLY)); then
    printf 'done: personal ops cron jobs upserted.\n'
  else
    printf 'done: dry-run only; rerun with --apply to persist.\n'
  fi
}

main "$@"
