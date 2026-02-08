#!/usr/bin/env bash
set -euo pipefail

# Safe gateway diagnostics (read-only).
#
# Goal: fast triage without dumping secrets.

hr() { printf '\n== %s ==\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

if ! have openclaw; then
  echo "openclaw not found in PATH"
  exit 1
fi

hr "Gateway Health"
openclaw health || true

hr "Gateway Service Status"
openclaw gateway status || true

hr "Channels (Probed)"
if have jq; then
  openclaw channels status --probe --json 2>/dev/null \
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
    | jq -r '.' || true
else
  openclaw channels status --probe 2>/dev/null || true
fi

hr "Recent Gateway Logs (tail 80)"
openclaw logs --tail 80 2>/dev/null || true

