#!/usr/bin/env bash
set -euo pipefail

# Mochat integration self-check (safe to run; does not print tokens).
#
# Checks:
# - local credentials file exists, is valid JSON, and has tight permissions
# - OpenClaw Mochat plugin installed + enabled
# - OpenClaw config has a locked-down channels.mochat config (no wildcards by default)
# - Mochat API token works for owner lookup + session detail

have() { command -v "$1" >/dev/null 2>&1; }

fail=0

cred_dir="$HOME/.config/mochat"
cred_file="$cred_dir/credentials.json"
cfg_file="$HOME/.openclaw/openclaw.json"
openclaw_bin="${OPENCLAW_BIN:-}"
OPENCLAW_CMD=""

say() { printf '%s\n' "$*"; }
bad() { say "FAIL: $*"; fail=1; }
ok() { say "OK: $*"; }

if ! have jq; then
  bad "jq not found (required)"
else
  ok "jq present"
fi

if [ ! -f "$cred_file" ]; then
  bad "missing credentials: $cred_file"
else
  ok "credentials file exists"
  if jq -e '.' "$cred_file" >/dev/null 2>&1; then
    ok "credentials JSON parses"
  else
    bad "credentials JSON invalid"
  fi
fi

if [ -d "$cred_dir" ]; then
  # macOS stat format; fall back quietly.
  if have stat; then
    perms_dir="$(stat -f '%Sp' "$cred_dir" 2>/dev/null || true)"
    perms_file="$(stat -f '%Sp' "$cred_file" 2>/dev/null || true)"
    [ "$perms_dir" = "drwx------" ] && ok "credentials dir perms tight ($perms_dir)" || bad "credentials dir perms not tight ($perms_dir)"
    [ "$perms_file" = "-rw-------" ] && ok "credentials file perms tight ($perms_file)" || bad "credentials file perms not tight ($perms_file)"
  fi
fi

if [[ -z "${openclaw_bin}" ]]; then
  # Prefer wrapper so agent tool environments without user PATH still work.
  openclaw_bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaww.sh"
fi

if [[ -x "${openclaw_bin}" ]]; then
  OPENCLAW_CMD="${openclaw_bin}"
  ok "openclaw wrapper present (${openclaw_bin})"
elif have openclaw; then
  OPENCLAW_CMD="openclaw"
  ok "openclaw present"
else
  bad "openclaw not found (tried OPENCLAW_BIN, scripts/openclaww.sh, and PATH)"
fi

if [[ -n "${OPENCLAW_CMD}" ]]; then
  if "${OPENCLAW_CMD}" plugins info mochat >/dev/null 2>&1; then
    ok "OpenClaw Mochat plugin discovered"
  else
    bad "OpenClaw Mochat plugin not found (run: openclaw plugins install @jiabintang/mochat)"
  fi

  if "${OPENCLAW_CMD}" config get plugins.entries.mochat.enabled 2>/dev/null | grep -Eq '^true$'; then
    ok "OpenClaw Mochat plugin enabled"
  else
    bad "OpenClaw Mochat plugin not enabled (run: openclaw plugins enable mochat)"
  fi
fi

if [ ! -f "$cfg_file" ]; then
  bad "missing OpenClaw config: $cfg_file"
else
  ok "OpenClaw config file exists"
  if have jq; then
    if jq -e '.channels.mochat' "$cfg_file" >/dev/null 2>&1; then
      ok "channels.mochat exists in config"
    else
      bad "channels.mochat missing in config"
    fi

    # Safety policy: avoid wildcards by default. DMs should be locked to the owner session.
    if jq -e '(.channels.mochat.sessions // []) | any(. == "*")' "$cfg_file" >/dev/null 2>&1; then
      bad "channels.mochat.sessions contains wildcard (*)"
    else
      ok "channels.mochat.sessions has no wildcard"
    fi
    if jq -e '(.channels.mochat.panels // []) | length == 0' "$cfg_file" >/dev/null 2>&1; then
      ok "channels.mochat.panels empty (safe default)"
    else
      bad "channels.mochat.panels not empty (public surface enabled)"
    fi
  fi
fi

if [ -f "$cred_file" ] && have jq; then
  token="$(jq -r '.token // empty' "$cred_file")"
  [ -n "$token" ] || bad "token missing in credentials.json"

  session_id=""
  if [ -f "$cfg_file" ]; then
    session_id="$(jq -r '.channels.mochat.sessions[0] // empty' "$cfg_file" 2>/dev/null || true)"
  fi

  if [ -n "$token" ] && have curl; then
    # Owner must be bound for safe operation (verified DM authority).
    if curl -fsS -X POST https://mochat.io/api/claw/agents/owner \
      -H 'Content-Type: application/json' \
      -H "X-Claw-Token: ${token}" >/dev/null; then
      ok "Mochat token works for /agents/owner"
    else
      bad "Mochat token failed for /agents/owner"
    fi

    if [ -n "$session_id" ]; then
      if curl -fsS -X POST https://mochat.io/api/claw/sessions/detail \
        -H 'Content-Type: application/json' \
        -H "X-Claw-Token: ${token}" \
        -d "{\"sessionId\":\"${session_id}\"}" >/dev/null; then
        ok "Mochat token works for /sessions/detail (configured session)"
      else
        bad "Mochat token failed for /sessions/detail (configured session)"
      fi
    else
      bad "No sessionId configured in channels.mochat.sessions"
    fi
  fi
fi

if [ "$fail" -eq 0 ]; then
  ok "mochat self-check passed"
  exit 0
fi

exit 1
