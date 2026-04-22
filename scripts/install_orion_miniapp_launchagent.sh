#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
template="${repo_root}/scripts/orion_miniapp_launchagent.plist"
target="${HOME}/Library/LaunchAgents/com.openclaw.orion.miniapp.plist"
mkdir -p "${HOME}/Library/LaunchAgents"

python3 - "$template" "$target" "$repo_root" "$HOME" <<'PY'
from pathlib import Path
import sys

template = Path(sys.argv[1]).read_text(encoding="utf-8")
target = Path(sys.argv[2])
repo_root = sys.argv[3]
home = sys.argv[4]
payload = template.replace("__REPO_ROOT__", repo_root).replace("__HOME__", home)
target.write_text(payload, encoding="utf-8")
PY

launchctl bootout "gui/$(id -u)" "${target}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "${target}"
launchctl enable "gui/$(id -u)/com.openclaw.orion.miniapp"
launchctl kickstart -k "gui/$(id -u)/com.openclaw.orion.miniapp"

echo "Installed: ${target}"
echo "Log: ${HOME}/Library/Logs/com.openclaw.orion.miniapp.log"
