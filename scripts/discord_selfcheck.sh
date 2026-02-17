#!/usr/bin/env bash
set -euo pipefail

# Discord integration self-check (safe to run; does not print tokens).
#
# Checks:
# - OpenClaw present
# - Discord plugin discovered + enabled
# - OpenClaw config has channels.discord configured + locked down (no wildcards by default)
# - Channel probe succeeds (best-effort)

have() { command -v "$1" >/dev/null 2>&1; }

fail=0

cfg_file="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
openclaw_bin="${OPENCLAW_BIN:-}"
OPENCLAW_CMD=""

say() { printf '%s\n' "$*"; }
bad() { say "FAIL: $*"; fail=1; }
ok() { say "OK: $*"; }

if ! have jq; then
  say "WARN: jq not found (some checks skipped)"
else
  ok "jq present"
fi

if [[ -z "${openclaw_bin}" ]]; then
  OPENCLAW_CMD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaww.sh"
else
  OPENCLAW_CMD="${openclaw_bin}"
fi

if [[ -x "${OPENCLAW_CMD}" ]]; then
  ok "openclaw wrapper present (${OPENCLAW_CMD})"
elif have openclaw; then
  OPENCLAW_CMD="openclaw"
  ok "openclaw present"
else
  bad "openclaw not found (tried OPENCLAW_BIN, scripts/openclaww.sh, and PATH)"
fi

if [[ -n "${OPENCLAW_CMD}" ]]; then
  if "${OPENCLAW_CMD}" plugins info discord >/dev/null 2>&1; then
    ok "OpenClaw Discord plugin discovered"
  else
    bad "OpenClaw Discord plugin not found (it should be bundled; check your OpenClaw install)"
  fi

  if have jq && "${OPENCLAW_CMD}" plugins list --json >/dev/null 2>&1; then
    if "${OPENCLAW_CMD}" plugins list --json | jq -e '.plugins[] | select(.id=="discord") | .enabled==true' >/dev/null 2>&1; then
      ok "OpenClaw Discord plugin enabled"
    else
      bad "OpenClaw Discord plugin not enabled (run: openclaw plugins enable discord)"
    fi
  else
    say "WARN: could not verify plugin enabled state (jq or plugins list --json unavailable)"
  fi
fi

if [[ ! -f "${cfg_file}" ]]; then
  bad "missing OpenClaw config: ${cfg_file}"
else
  ok "OpenClaw config file exists (${cfg_file})"
  if have jq; then
    if jq -e '.channels.discord' "${cfg_file}" >/dev/null 2>&1; then
      ok "channels.discord exists in config"
    else
      bad "channels.discord missing in config"
    fi

    if jq -e '.channels.discord.enabled == true' "${cfg_file}" >/dev/null 2>&1; then
      ok "channels.discord.enabled true"
    else
      bad "channels.discord.enabled not true"
    fi

    # Safety posture: prefer allowlist or pairing for DMs and allowlist for guilds.
    dm_policy="$(jq -r '.channels.discord.dm.policy // empty' "${cfg_file}" 2>/dev/null || true)"
    [[ -n "${dm_policy}" ]] && ok "channels.discord.dm.policy=${dm_policy}" || say "WARN: channels.discord.dm.policy not set"
    gp="$(jq -r '.channels.discord.groupPolicy // empty' "${cfg_file}" 2>/dev/null || true)"
    [[ -n "${gp}" ]] && ok "channels.discord.groupPolicy=${gp}" || say "WARN: channels.discord.groupPolicy not set"

    # Reliability: replyToMode=first can end up targeting Discord's thread-starter system message
    # when autoThread is enabled, which can suppress visible replies.
    rtm="$(jq -r '.channels.discord.replyToMode // empty' "${cfg_file}" 2>/dev/null || true)"
    auto_threads="$(jq -r '[.channels.discord.guilds // {} | to_entries[]? | .value.channels // {} | to_entries[]? | select(.value.autoThread==true)] | length' "${cfg_file}" 2>/dev/null || echo 0)"
    if [[ "${rtm}" == "first" && "${auto_threads}" != "0" ]]; then
      say "WARN: channels.discord.replyToMode=first + autoThread=true may suppress replies in new threads; recommend: openclaw config set channels.discord.replyToMode off"
    fi
  fi
fi

if [[ -n "${OPENCLAW_CMD}" ]]; then
  # Probe is best-effort; it may fail if token is missing or gateway is stopped.
  if have jq; then
    probe="$("${OPENCLAW_CMD}" channels status --probe --json 2>/dev/null || true)"
    if [[ -n "${probe}" ]]; then
      configured="$(printf '%s' "${probe}" | jq -r '.channels.discord.configured // empty' 2>/dev/null || true)"
      running="$(printf '%s' "${probe}" | jq -r '.channels.discord.running // empty' 2>/dev/null || true)"
      [[ -n "${configured}" ]] && ok "discord configured=${configured}" || say "WARN: discord configured unknown"
      [[ -n "${running}" ]] && ok "discord running=${running}" || say "WARN: discord running unknown"
    else
      say "WARN: could not probe channels (gateway stopped or discord not enabled)"
    fi
  else
    "${OPENCLAW_CMD}" channels status --probe >/dev/null 2>&1 || say "WARN: channels probe failed"
  fi
fi

if [[ "${fail}" -eq 0 ]]; then
  ok "discord self-check passed"
  exit 0
fi

exit 1
