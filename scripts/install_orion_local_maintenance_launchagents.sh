#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:-}"
if [[ -z "${repo_root}" ]]; then
  if repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    true
  else
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  fi
fi

runner="${repo_root}/scripts/orion_local_maintenance_runner.sh"
launch_agents_dir="${HOME}/Library/LaunchAgents"
logs_dir="${HOME}/Library/Logs"
overlap_guard="${repo_root}/scripts/orion_scheduler_overlap_guard.py"
stale_launch_agents=(
  "ai.orion.inbox_packet_runner"
  "com.openclaw.orion.assistant_task_loop"
)

mkdir -p "${launch_agents_dir}" "${logs_dir}"

if [[ ! -f "${runner}" ]]; then
  echo "Runner script not found: ${runner}" >&2
  exit 1
fi
if [[ ! -f "${overlap_guard}" ]]; then
  echo "Overlap guard script not found: ${overlap_guard}" >&2
  exit 1
fi

remove_stale_launch_agents() {
  local existing_label
  for existing_label in "${stale_launch_agents[@]}"; do
    local existing_plist="${launch_agents_dir}/${existing_label}.plist"
    if [[ -f "${existing_plist}" ]]; then
      launchctl bootout "gui/$(id -u)" "${existing_plist}" >/dev/null 2>&1 || true
      rm -f "${existing_plist}"
      echo "Removed stale LaunchAgent: ${existing_plist}"
    fi
  done
}

install_plist() {
  local label="$1"
  local schedule_kind="$2"
  local schedule_value="$3"
  local job_key="$4"
  local plist_target="${launch_agents_dir}/${label}.plist"
  local log_path="${logs_dir}/${label}.log"

  {
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${runner}</string>
    <string>${job_key}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${repo_root}</string>
EOF
    if [[ "${schedule_kind}" == "interval" ]]; then
      cat <<EOF
  <key>StartInterval</key>
  <integer>${schedule_value}</integer>
EOF
    else
      cat <<EOF
  <key>StartCalendarInterval</key>
  ${schedule_value}
EOF
    fi
    cat <<EOF
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log_path}</string>
  <key>StandardErrorPath</key>
  <string>${log_path}</string>
</dict>
</plist>
EOF
  } > "${plist_target}"

  launchctl bootout "gui/$(id -u)" "${plist_target}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "${plist_target}"
  launchctl enable "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
  launchctl kickstart -k "gui/$(id -u)/${label}" >/dev/null 2>&1 || true

  echo "Installed LaunchAgent: ${plist_target}"
}

disable_cron_by_name() {
  local name="$1"
  local matches
  matches="$(openclaw cron list --all --json 2>/dev/null | jq -r --arg name "${name}" '.jobs[]? | select(.name == $name and .enabled == true) | .id')"
  if [[ -n "${matches}" ]]; then
    while IFS= read -r job_id; do
      [[ -n "${job_id}" ]] || continue
      openclaw cron disable "${job_id}" >/dev/null
      echo "Disabled duplicate OpenClaw cron job: ${job_id} (${name})"
    done <<< "${matches}"
  fi
}

remove_stale_launch_agents

install_plist "ai.orion.inbox_result_notify" "interval" "120" "assistant-inbox-notify"
install_plist "com.openclaw.orion.assistant_email_triage" "interval" "300" "assistant-email-triage"
install_plist "com.openclaw.orion.assistant_agenda_refresh" "interval" "900" "assistant-agenda-refresh"
install_plist "com.openclaw.orion.orion_error_review" "calendar" "<dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>15</integer></dict>" "orion-error-review"
install_plist "com.openclaw.orion.orion_session_maintenance" "calendar" "<dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>45</integer></dict>" "orion-session-maintenance"
install_plist "com.openclaw.orion.orion_ops_bundle" "calendar" "<dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>" "orion-ops-bundle"
install_plist "com.openclaw.orion.orion_judgment_layer" "calendar" "<dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>40</integer></dict>" "orion-judgment-layer"
install_plist "com.openclaw.orion.orion_yeet_worktree" "interval" "43200" "orion-yeet-worktree"

disable_cron_by_name "assistant-inbox-notify"
disable_cron_by_name "assistant-email-triage"
disable_cron_by_name "assistant-task-loop"
disable_cron_by_name "assistant-agenda-refresh"
disable_cron_by_name "orion-error-review"
disable_cron_by_name "orion-session-maintenance"
disable_cron_by_name "orion-ops-bundle"
disable_cron_by_name "orion-judgment-layer"

python3 "${overlap_guard}" \
  --launch-agents-dir "${launch_agents_dir}" \
  --cron-jobs "${HOME}/.openclaw/cron/jobs.json"

echo "Installed ORION local maintenance LaunchAgents bundle."
