#!/usr/bin/env bash
set -euo pipefail

# STRATUS: safe, read-only health check suitable for Task Packets / automation.
#
# Output is intentionally concise and stable:
# - CHECKS: bullet list
# - NEXT: single recommended next step (if any)
#
# Exit codes:
# - 0: gateway health OK
# - 1: gateway health FAIL
# - 2: openclaw missing / usage error

have() { command -v "$1" >/dev/null 2>&1; }

skip_host=0
if [[ "${STRATUS_SKIP_HOST:-}" == "1" ]]; then
  skip_host=1
fi

for arg in "$@"; do
  case "$arg" in
    --no-host) skip_host=1 ;;
    -h|--help)
      cat <<'TXT'
Usage:
  scripts/stratus_healthcheck.sh [--no-host]

Options:
  --no-host   Skip host resource checks (useful for tests/CI).
TXT
      exit 2
      ;;
    *) ;;
  esac
done

if ! have openclaw; then
  printf 'CHECKS:\n'
  printf -- '- openclaw: MISSING\n'
  printf 'NEXT:\n'
  printf -- '- Install/open PATH to openclaw.\n'
  exit 2
fi

tmp="${TMPDIR:-/tmp}/stratus_health.$$.$RANDOM.out"
trap 'rm -f "$tmp" 2>/dev/null || true' EXIT

health="FAIL"
if openclaw health >"$tmp" 2>&1; then
  health="OK"
fi

gateway_status="unknown"
if openclaw gateway status >/dev/null 2>&1; then
  gateway_status="OK"
else
  gateway_status="FAIL"
fi

printf 'CHECKS:\n'
printf -- '- gateway health: %s\n' "$health"
printf -- '- gateway service: %s\n' "$gateway_status"

if [[ "$skip_host" -eq 0 ]]; then
  # Keep these intentionally lightweight and OS-agnostic.
  disk_line="$(df -h / 2>/dev/null | tail -n 1 || true)"
  if [[ -n "$disk_line" ]]; then
    disk_free="$(printf '%s' "$disk_line" | awk '{print $4}' 2>/dev/null || true)"
    [[ -n "$disk_free" ]] && printf -- '- host disk: %s free on /\n' "$disk_free"
  fi
fi

if [[ "$health" == "OK" ]]; then
  printf 'NEXT:\n'
  printf -- '- No action needed.\n'
  exit 0
fi

printf -- '- health output: %s\n' "$(sed -n '1p' "$tmp" 2>/dev/null | tr -d '\r' || true)"
printf 'NEXT:\n'
printf -- '- Run scripts/diagnose_gateway.sh, then consider: openclaw gateway restart\n'
exit 1

