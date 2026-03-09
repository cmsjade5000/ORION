#!/usr/bin/env bash
set -euo pipefail

if ! command -v openclaw >/dev/null 2>&1; then
  echo "SKIP: openclaw is not installed"
  exit 0
fi

config_path="$(openclaw config file 2>/dev/null || true)"
if [[ -z "${config_path}" ]]; then
  echo "SKIP: openclaw config path is unavailable"
  exit 0
fi

config_path="${config_path/#\~/$HOME}"
if [[ ! -f "${config_path}" ]]; then
  echo "SKIP: openclaw config file not found at ${config_path}"
  exit 0
fi

openclaw config validate --json
