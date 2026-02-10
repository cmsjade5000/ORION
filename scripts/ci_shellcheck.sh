#!/usr/bin/env bash
set -euo pipefail

# CI: run ShellCheck over repo bash scripts.
#
# We treat warnings/errors as failures; "info" is ignored to reduce noise.

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "ERROR: shellcheck not found in PATH" >&2
  echo "Install it (macOS): brew install shellcheck" >&2
  echo "Install it (Ubuntu): sudo apt-get install -y shellcheck" >&2
  exit 2
fi

files=()
while IFS= read -r f; do
  [ -n "$f" ] || continue
  files+=("$f")
done < <(
  (
    find scripts -maxdepth 2 -type f \( -name "*.sh" -o -path "scripts/aegis_remote/*" \)
    echo status.sh
  ) | sort -u
)

if [ "${#files[@]}" -eq 0 ]; then
  echo "ERROR: no scripts found for shellcheck" >&2
  exit 2
fi

shellcheck -S warning -x --shell=bash "${files[@]}"
