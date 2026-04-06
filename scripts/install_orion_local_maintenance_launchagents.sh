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

mkdir -p "${launch_agents_dir}" "${logs_dir}"

if [[ ! -f "${runner}" ]]; then
  echo "Runner script not found: ${runner}" >&2
  exit 1
fi

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

install_plist "ai.orion.inbox_result_notify" "interval" "120" "assistant-inbox-notify"
install_plist "com.openclaw.orion.assistant_task_loop" "interval" "300" "assistant-task-loop"
install_plist "com.openclaw.orion.assistant_agenda_refresh" "interval" "900" "assistant-agenda-refresh"
install_plist "com.openclaw.orion.orion_error_review" "calendar" "<dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>15</integer></dict>" "orion-error-review"
install_plist "com.openclaw.orion.orion_session_maintenance" "calendar" "<dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>45</integer></dict>" "orion-session-maintenance"
install_plist "com.openclaw.orion.orion_ops_bundle" "calendar" "<dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>" "orion-ops-bundle"
install_plist "com.openclaw.orion.kalshi_ref_arb_digest" "calendar" "<array><dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict><dict><key>Hour</key><integer>15</integer><key>Minute</key><integer>0</integer></dict><dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>0</integer></dict></array>" "kalshi-ref-arb-digest"
install_plist "com.openclaw.orion.kalshi_digest_delivery_guard" "calendar" "<dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>12</integer></dict>" "kalshi-digest-delivery-guard"
install_plist "com.openclaw.orion.kalshi_digest_reliability_daily" "calendar" "<dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>5</integer></dict>" "kalshi-digest-reliability-daily"
install_plist "com.openclaw.orion.orion_reliability_daily" "calendar" "<dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>10</integer></dict>" "orion-reliability-daily"
install_plist "com.openclaw.orion.orion_route_hygiene_daily" "calendar" "<dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>12</integer></dict>" "orion-route-hygiene-daily"
install_plist "com.openclaw.orion.orion_lane_hotspots_daily" "calendar" "<dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>14</integer></dict>" "orion-lane-hotspots-daily"
install_plist "com.openclaw.orion.orion_stop_gate_daily" "calendar" "<dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>16</integer></dict>" "orion-stop-gate-daily"
install_plist "com.openclaw.orion.orion_monthly_scorecard_daily" "calendar" "<dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>20</integer></dict>" "orion-monthly-scorecard-daily"
install_plist "com.openclaw.orion.orion_skill_discovery_weekly" "calendar" "<dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>" "orion-skill-discovery-weekly"

disable_cron_by_name "assistant-inbox-notify"
disable_cron_by_name "assistant-task-loop"
disable_cron_by_name "assistant-agenda-refresh"
disable_cron_by_name "orion-error-review"
disable_cron_by_name "orion-session-maintenance"
disable_cron_by_name "orion-ops-bundle"
disable_cron_by_name "kalshi-ref-arb-digest"
disable_cron_by_name "kalshi-digest-delivery-guard"
disable_cron_by_name "kalshi-digest-reliability-daily"
disable_cron_by_name "orion-reliability-daily"
disable_cron_by_name "orion-route-hygiene-daily"
disable_cron_by_name "orion-lane-hotspots-daily"
disable_cron_by_name "orion-stop-gate-daily"
disable_cron_by_name "orion-monthly-scorecard-daily"
disable_cron_by_name "orion-skill-discovery-weekly"

echo "Installed ORION local maintenance LaunchAgents bundle."
