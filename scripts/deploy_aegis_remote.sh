#!/usr/bin/env bash
set -euo pipefail

# Deploy AEGIS remote scripts (Hetzner) from this repo to /usr/local/bin.
#
# This is intentionally conservative:
# - copies only known script files
# - requires SSH access
# - restarts only the monitor/sentinel services (not tailscale, not the gateway)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

host="${AEGIS_HOST:-100.75.104.54}"
user="${AEGIS_SSH_USER:-root}"
dest="/usr/local/bin"
do_restart=1

usage() {
  cat <<'TXT' >&2
Usage:
  scripts/deploy_aegis_remote.sh [--host <ip>] [--user <user>] [--no-restart]

Env:
  AEGIS_HOST       Default host (default: 100.75.104.54)
  AEGIS_SSH_USER   Default ssh user (default: root)
TXT
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="${2-}"; shift 2 ;;
    --user) user="${2-}"; shift 2 ;;
    --no-restart) do_restart=0; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ -z "$host" ]] || [[ -z "$user" ]]; then
  usage
fi

src_dir="$ROOT/scripts/aegis_remote"
files=(
  "$src_dir/aegis-monitor-orion"
  "$src_dir/aegis-sentinel"
  "$src_dir/aegis-defend"
  "$src_dir/lib_alert_format.sh"
)

for f in "${files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing file: $f" >&2
    exit 2
  fi
done

echo "Deploying AEGIS scripts to ${user}@${host}:${dest}/"
scp "${files[@]}" "${user}@${host}:${dest}/"

echo "Setting permissions..."
ssh "${user}@${host}" "chmod 0755 ${dest}/aegis-monitor-orion ${dest}/aegis-sentinel ${dest}/aegis-defend; chmod 0644 ${dest}/lib_alert_format.sh"

if [[ "$do_restart" -eq 1 ]]; then
  echo "Restarting services..."
  ssh "${user}@${host}" "systemctl restart aegis-monitor-orion.service aegis-sentinel.service"
fi

echo "AEGIS_DEPLOY_OK host=${host}"

