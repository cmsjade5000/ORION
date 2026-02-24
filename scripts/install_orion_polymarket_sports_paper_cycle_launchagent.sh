#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:-}"
if [[ -z "${repo_root}" ]]; then
  if [[ -d "${HOME}/Desktop/ORION" ]]; then
    repo_root="${HOME}/Desktop/ORION"
  elif repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    true
  else
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  fi
fi

launch_agents_dir="${HOME}/Library/LaunchAgents"
plist_name="com.openclaw.orion.polymarket_sports_paper_cycle.plist"
plist_target="${launch_agents_dir}/${plist_name}"
template="${repo_root}/scripts/orion_polymarket_sports_paper_cycle_launchagent.plist"
cycle_script="${repo_root}/scripts/polymarket_sports_paper_cycle.py"

mkdir -p "${launch_agents_dir}"

if [[ ! -f "${template}" ]]; then
  echo "Template plist not found: ${template}" >&2
  exit 1
fi

if [[ ! -f "${cycle_script}" ]]; then
  echo "Sports cycle script not found: ${cycle_script}" >&2
  exit 1
fi

sed "s|__REPO_ROOT__|${repo_root}|g" "${template}" > "${plist_target}"

launchctl bootout "gui/$(id -u)" "${plist_target}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "${plist_target}"
launchctl enable "gui/$(id -u)/com.openclaw.orion.polymarket_sports_paper_cycle" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$(id -u)/com.openclaw.orion.polymarket_sports_paper_cycle" >/dev/null 2>&1 || true

echo "Installed LaunchAgent: ${plist_target}"
echo "Label: com.openclaw.orion.polymarket_sports_paper_cycle"
echo "Cadence: every 60 seconds"
echo "Log: ${HOME}/Library/Logs/orion_polymarket_sports_paper_cycle.log"
