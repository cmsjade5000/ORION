#!/usr/bin/env bash
set -euo pipefail

if ! command -v openclaw >/dev/null 2>&1; then
  echo "SKIP: openclaw is not installed"
  exit 0
fi

check_cmd() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "OK: ${label}"
    return 0
  fi
  return 1
}

check_cmd "config validate" openclaw config validate --help || {
  echo "FAIL: missing 'openclaw config validate'" >&2
  exit 2
}

check_cmd "sessions cleanup" openclaw sessions cleanup --help || {
  echo "FAIL: missing 'openclaw sessions cleanup'" >&2
  exit 2
}

check_cmd "agents bindings" openclaw agents bindings --help || {
  echo "FAIL: missing 'openclaw agents bindings'" >&2
  exit 2
}

if check_cmd "update status" openclaw update status --help; then
  :
elif check_cmd "update --json status" openclaw update --json status --help; then
  :
else
  echo "FAIL: missing both update status commands: 'openclaw update status' and 'openclaw update --json status'" >&2
  exit 2
fi

echo "openclaw-cli-compat: PASS"
