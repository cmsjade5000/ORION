#!/usr/bin/env bash
set -euo pipefail

# Local wrapper for ORION/Cory to invoke the allowlisted defender on the Hetzner AEGIS host.
# Remote executor is /usr/local/bin/aegis-defend (installed from scripts/aegis_remote/aegis-defend).

AEGIS_HOST="${AEGIS_HOST:-100.75.104.54}"
AEGIS_SSH_USER="${AEGIS_SSH_USER:-root}"
AEGIS_SSH_STRICT_HOST_KEY_CHECKING="${AEGIS_SSH_STRICT_HOST_KEY_CHECKING:-yes}"
AEGIS_SSH_KNOWN_HOSTS="${AEGIS_SSH_KNOWN_HOSTS:-${HOME}/.ssh/known_hosts}"

SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o "StrictHostKeyChecking=${AEGIS_SSH_STRICT_HOST_KEY_CHECKING}"
  -o "UserKnownHostsFile=${AEGIS_SSH_KNOWN_HOSTS}"
)

if [ $# -lt 1 ]; then
  echo "Usage: $0 <list|show|approve|run> ..." >&2
  exit 2
fi

remote_cmd="/usr/local/bin/aegis-defend"
for arg in "$@"; do
  printf -v quoted '%q' "$arg"
  remote_cmd+=" ${quoted}"
done

ssh "${SSH_OPTS[@]}" "${AEGIS_SSH_USER}@${AEGIS_HOST}" "exec ${remote_cmd}"
