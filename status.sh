#!/usr/bin/env bash
set -euo pipefail

hr() { printf '\n== %s ==\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

AEGIS_HOST="${AEGIS_HOST:-100.75.104.54}"
AEGIS_SSH_USER="${AEGIS_SSH_USER:-root}"

hr "ORION Gateway Health (Local)"
if have openclaw; then
  if openclaw health >/tmp/orion_health.out 2>&1; then
    printf 'health: OK\n'
  else
    printf 'health: FAIL\n'
    sed -n '1,80p' /tmp/orion_health.out || true
  fi
else
  printf 'openclaw: not found in PATH\n'
fi

hr "Configured Channels (Local)"
if have openclaw; then
  if have jq; then
    # Avoid printing secrets; OpenClaw config should use tokenFile paths, but we still redact obvious token-ish keys.
    openclaw config get channels --json 2>/dev/null \
      | jq 'walk(
          if type=="object" then
            with_entries(
              if (
                (.key|test("(token|secret|apikey|apiKey|privateKey|key)$"; "i"))
                and (.key|test("File$"; "i")|not)
              ) then
                .value = "<redacted>"
              else
                .
              end
            )
          else
            .
          end
        )' \
      | jq -r '
          to_entries
          | map(
              "\(.key): enabled=\(.value.enabled // "unknown")"
              + (if .value.tokenFile then " tokenFile=\(.value.tokenFile)" else "" end)
              + (if .value.allowFrom then " allowFrom=\(.value.allowFrom|tostring)" else "" end)
              + (if .value.groups then " groups=\(.value.groups|keys|tostring)" else "" end)
              + (if .value.defaultTarget then " defaultTarget=\(.value.defaultTarget)" else "" end)
            )
          | .[]
        ' || true
  else
    printf 'jq: missing (skipping structured channel dump)\n'
    openclaw config get channels --json 2>/dev/null | sed -n '1,80p' || true
  fi
else
  printf 'openclaw: not found\n'
fi

hr "Host Resources (Local)"
uname_s="$(uname -s 2>/dev/null || true)"
if [ "$uname_s" = "Darwin" ]; then
  printf 'time: %s\n' "$(date)"
  printf 'uptime: %s\n' "$(uptime)"
  printf '\n-- disk (df -h /) --\n'
  df -h / || true
  if have memory_pressure; then
    printf '\n-- memory_pressure -Q --\n'
    memory_pressure -Q 2>/dev/null || true
  else
    printf '\n-- vm_stat (first 12 lines) --\n'
    vm_stat 2>/dev/null | sed -n '1,12p' || true
  fi
  if have ps; then
    printf '\n-- openclaw processes (ps) --\n'
    if have rg; then
      ps aux | rg -n "openclaw" -S | sed -n '1,12p' || true
    else
      ps aux | grep -i openclaw | head -n 12 || true
    fi
  fi
else
  printf 'time: %s\n' "$(date)"
  printf 'uptime: %s\n' "$(uptime 2>/dev/null || true)"
  printf '\n-- disk (df -h) --\n'
  df -h 2>/dev/null | sed -n '1,12p' || true
fi

hr "Local Gateway Logs (tail 20)"
for f in "$HOME/.openclaw/logs/gateway.log" "$HOME/.openclaw/logs/gateway.err.log"; do
  if [ -f "$f" ]; then
    printf '\n-- %s --\n' "$f"
    tail -n 20 "$f" || true
  fi
done

hr "AEGIS (Remote) last_ok + logs (tail 20)"
if have ssh; then
  if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "${AEGIS_SSH_USER}@${AEGIS_HOST}" 'true' >/dev/null 2>&1; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${AEGIS_SSH_USER}@${AEGIS_HOST}" 'set -euo pipefail
echo "host: $(hostname)"
echo "tailscale: $(tailscale status 2>/dev/null | head -n 2 | tail -n 1 || true)"
for u in openclaw-aegis.service aegis-monitor-orion.timer aegis-sentinel.timer tailscaled; do
  a=$(systemctl is-active "$u" 2>/dev/null || true)
  e=$(systemctl is-enabled "$u" 2>/dev/null || true)
  echo "$u: active=$a enabled=$e"
done
m_ok=""; s_ok=""
[ -f /var/lib/aegis-monitor/last_ok ] && m_ok=$(cat /var/lib/aegis-monitor/last_ok || true)
[ -f /var/lib/aegis-sentinel/last_ok ] && s_ok=$(cat /var/lib/aegis-sentinel/last_ok || true)
echo "monitor.last_ok: ${m_ok:-missing}"
echo "sentinel.last_ok: ${s_ok:-missing}"

echo ""
echo "-- /var/log/aegis-monitor/monitor.log (tail 20) --"
tail -n 20 /var/log/aegis-monitor/monitor.log 2>/dev/null || true
echo ""
echo "-- /var/log/aegis-sentinel/sentinel.log (tail 20) --"
tail -n 20 /var/log/aegis-sentinel/sentinel.log 2>/dev/null || true

if [ -f /var/lib/aegis-monitor/orion_restart_guard.lock ]; then
  echo ""
  echo "restart_guard: ACTIVE (/var/lib/aegis-monitor/orion_restart_guard.lock)"
fi
if [ -f /var/lib/aegis-monitor/incidents.md ]; then
  echo ""
  echo "-- /var/lib/aegis-monitor/incidents.md (tail 20) --"
  tail -n 20 /var/lib/aegis-monitor/incidents.md 2>/dev/null || true
fi
if [ -f /var/lib/aegis-sentinel/incidents.md ]; then
  echo ""
  echo "-- /var/lib/aegis-sentinel/incidents.md (tail 20) --"
  tail -n 20 /var/lib/aegis-sentinel/incidents.md 2>/dev/null || true
fi
'
  else
    printf 'AEGIS: unreachable (ssh failed) host=%s\n' "$AEGIS_HOST"
  fi
else
  printf 'ssh: missing\n'
fi

hr "Repo"
printf 'root: %s\n' "$ROOT"
