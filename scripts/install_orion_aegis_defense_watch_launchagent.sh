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
plist_name="com.openclaw.orion.aegis_defense_watch.plist"
plist_target="${launch_agents_dir}/${plist_name}"
watch_script="${repo_root}/scripts/aegis_defense_watch.sh"

mkdir -p "${launch_agents_dir}"

if [[ ! -x "${watch_script}" ]]; then
  echo "Watch script not found or not executable: ${watch_script}" >&2
  echo "Run this installer with the ORION repo path, e.g.:" >&2
  echo "  scripts/install_orion_aegis_defense_watch_launchagent.sh /Users/corystoner/Desktop/ORION" >&2
  exit 1
fi

sed "s|__REPO_ROOT__|${repo_root}|g" \
  "${repo_root}/scripts/orion_aegis_defense_watch_launchagent.plist" > "${plist_target}"

launchctl unload "${plist_target}" >/dev/null 2>&1 || true
launchctl load "${plist_target}"

echo "Installed LaunchAgent: ${plist_target}"
echo "Logs: ${HOME}/Library/Logs/orion_aegis_defense_watch.log"

