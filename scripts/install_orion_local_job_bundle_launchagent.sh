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
legacy_plist="${launch_agents_dir}/com.openclaw.orion.local_job_bundle.plist"
maintenance_installer="${repo_root}/scripts/install_orion_local_maintenance_launchagents.sh"

if [[ -f "${legacy_plist}" ]]; then
  launchctl bootout "gui/$(id -u)" "${legacy_plist}" >/dev/null 2>&1 || true
  rm -f "${legacy_plist}"
  echo "Removed legacy LaunchAgent: ${legacy_plist}"
fi

echo "The local job bundle installer is deprecated."
echo "Handing off to the canonical maintenance LaunchAgents installer."

exec "${maintenance_installer}" "${repo_root}"
