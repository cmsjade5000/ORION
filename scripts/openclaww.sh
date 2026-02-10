#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run OpenClaw even when tool/sandbox PATH omits user-level bins.
#
# Env:
#   OPENCLAW_BIN  Optional absolute path override.

bin="${OPENCLAW_BIN:-}"
if [[ -n "${bin}" && -x "${bin}" ]]; then
  exec "${bin}" "$@"
fi

# npm-installed OpenClaw uses `#!/usr/bin/env node`.
# Some automation environments have a minimal PATH; ensure a standard node path is reachable.
if ! command -v node >/dev/null 2>&1; then
  for n in \
    "/usr/local/bin/node" \
    "/opt/homebrew/bin/node" \
    "${HOME}/.volta/bin/node"
  do
    if [[ -x "$n" ]]; then
      node_dir="$(dirname "$n")"
      PATH="${node_dir}:$PATH"
      export PATH
      break
    fi
  done
fi

if command -v openclaw >/dev/null 2>&1; then
  exec openclaw "$@"
fi

candidate=""
for p in \
  "${HOME}/.npm-global/bin/openclaw" \
  "/opt/homebrew/bin/openclaw" \
  "/usr/local/bin/openclaw" \
  "/usr/bin/openclaw"
do
  if [[ -x "$p" ]]; then
    candidate="$p"
    break
  fi
done

if [[ -z "$candidate" ]]; then
  echo "openclaw not found (PATH missing user bins; tried OPENCLAW_BIN and common install paths)" >&2
  exit 127
fi

exec "$candidate" "$@"
