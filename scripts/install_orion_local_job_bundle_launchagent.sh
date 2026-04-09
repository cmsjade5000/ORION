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

launch_agents_dir="${HOME}/Library/LaunchAgents"
plist_name="com.openclaw.orion.local_job_bundle.plist"
plist_target="${launch_agents_dir}/${plist_name}"
runner_script="${repo_root}/scripts/local_job_runner.py"
log_path="${HOME}/Library/Logs/orion_local_job_bundle.log"

duplicate_cron_names=(
  "assistant-agenda-refresh"
  "assistant-inbox-notify"
  "assistant-task-loop"
  "kalshi-ref-arb-digest"
  "kalshi-digest-delivery-guard"
  "kalshi-digest-reliability-daily"
  "orion-error-review"
  "orion-session-maintenance"
  "orion-ops-bundle"
  "orion-reliability-daily"
  "orion-route-hygiene-daily"
  "orion-lane-hotspots-daily"
  "orion-stop-gate-daily"
  "orion-monthly-scorecard-daily"
  "orion-skill-discovery-weekly"
)

mkdir -p "${launch_agents_dir}"
mkdir -p "$(dirname "${log_path}")"

if [[ ! -f "${runner_script}" ]]; then
  echo "Local job runner script not found: ${runner_script}" >&2
  exit 1
fi

cat > "${plist_target}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.openclaw.orion.local_job_bundle</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${runner_script}</string>
    <string>--repo-root</string>
    <string>${repo_root}</string>
    <string>--bundle</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${repo_root}</string>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${log_path}</string>
  <key>StandardErrorPath</key>
  <string>${log_path}</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "${plist_target}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "${plist_target}"
launchctl enable "gui/$(id -u)/com.openclaw.orion.local_job_bundle" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/com.openclaw.orion.local_job_bundle" >/dev/null 2>&1 || true

for cron_name in "${duplicate_cron_names[@]}"; do
  cron_matches="$(openclaw cron list --all --json 2>/dev/null | jq -r --arg name "${cron_name}" '.jobs[]? | select(.name == $name) | .id')"
  if [[ -z "${cron_matches}" ]]; then
    continue
  fi
  while IFS= read -r job_id; do
    [[ -n "${job_id}" ]] || continue
    openclaw cron disable "${job_id}" >/dev/null
    echo "Disabled duplicate OpenClaw cron job: ${job_id} (${cron_name})"
  done <<< "${cron_matches}"
done

echo "Installed LaunchAgent: ${plist_target}"
echo "Label: com.openclaw.orion.local_job_bundle"
echo "Cadence: every 60 seconds"
echo "Log: ${log_path}"
