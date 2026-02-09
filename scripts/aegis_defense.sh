#!/usr/bin/env bash
set -euo pipefail

# Local wrapper for ORION/Cory to invoke the allowlisted defender on the Hetzner AEGIS host.
# Remote executor is /usr/local/bin/aegis-defend (installed from scripts/aegis_remote/aegis-defend).

AEGIS_HOST="${AEGIS_HOST:-100.75.104.54}"
AEGIS_SSH_USER="${AEGIS_SSH_USER:-root}"

SSH_OPTS=(
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o StrictHostKeyChecking=accept-new
)

if [ $# -lt 1 ]; then
  echo "Usage: $0 <list|show|approve|run> ..." >&2
  exit 2
fi

ssh "${SSH_OPTS[@]}" "${AEGIS_SSH_USER}@${AEGIS_HOST}" "/usr/local/bin/aegis-defend $*"

