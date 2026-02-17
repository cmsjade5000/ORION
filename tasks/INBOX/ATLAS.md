# ATLAS Inbox

ATLAS is the ops/execution director. ORION should route ops/infra/workflow execution through ATLAS.

Append new Task Packets below. Spec: `docs/TASK_PACKET.md`.

## Packets

TASK_PACKET v1
Owner: ATLAS
Requester: ORION
Objective: Deploy the updated AEGIS `aegis-sentinel` script to the AEGIS host so routine Tailscale online/active churn no longer messages Cory.
Success Criteria:
- `/usr/local/bin/aegis-sentinel` on the AEGIS host reflects the updated Tailscale policy (membership vs status) and includes `AEGIS_TAILSCALE_STATUS_ALERT` defaulting to 0.
- `systemctl is-active aegis-sentinel.timer` and `systemctl is-active aegis-sentinel.service` are healthy after restart.
- `/var/log/aegis-sentinel/sentinel.log` shows an `OK: sentinel cycle` after deploy with no new errors.
Constraints:
- Do not change secrets/credentials.
- Keep a rollback path (backup the prior remote script before overwriting).
Inputs:
- /Users/corystoner/Desktop/ORION/scripts/deploy_aegis_remote.sh
- /Users/corystoner/Desktop/ORION/scripts/aegis_remote/aegis-sentinel
- AEGIS host defaults: `AEGIS_HOST=100.75.104.54`, `AEGIS_SSH_USER=root` (also referenced by /Users/corystoner/Desktop/ORION/status.sh)
Risks:
- Remote deploy restarts `aegis-sentinel.service` and may briefly delay monitoring; mitigate by verifying service health and logs immediately after.
Stop Gates:
- Any credential/key change or edits to `/etc/aegis-monitor.env`.
Output Format:
- Commands run + short verification output snippets (systemctl status lines + log tail).
Commands to run:
- ssh "${AEGIS_SSH_USER:-root}@${AEGIS_HOST:-100.75.104.54}" 'set -euo pipefail; if [ -f /usr/local/bin/aegis-sentinel ]; then cp -a /usr/local/bin/aegis-sentinel "/usr/local/bin/aegis-sentinel.bak.$(date -u +%Y%m%dT%H%M%SZ)"; fi'
- AEGIS_HOST="${AEGIS_HOST:-100.75.104.54}" AEGIS_SSH_USER="${AEGIS_SSH_USER:-root}" /Users/corystoner/Desktop/ORION/scripts/deploy_aegis_remote.sh
- ssh "${AEGIS_SSH_USER:-root}@${AEGIS_HOST:-100.75.104.54}" 'set -euo pipefail; systemctl --no-pager --full status aegis-sentinel.timer aegis-sentinel.service | sed -n "1,80p"; echo "---"; tail -n 80 /var/log/aegis-sentinel/sentinel.log'
