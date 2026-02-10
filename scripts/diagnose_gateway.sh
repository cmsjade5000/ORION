#!/usr/bin/env bash
set -euo pipefail

# Safe gateway diagnostics (read-only).
#
# Goal: fast triage without dumping secrets.

hr() { printf '\n== %s ==\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

OPENCLAW="${OPENCLAW_BIN:-}"
if [[ -z "${OPENCLAW}" ]]; then
  # Prefer wrapper so agent tool environments without user PATH still work.
  OPENCLAW="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openclaww.sh"
fi

hr "Gateway Health"
"$OPENCLAW" health || true

hr "Gateway Service Status"
"$OPENCLAW" gateway status || true

hr "Channels (Probed)"
if have jq; then
  "$OPENCLAW" channels status --probe --json 2>/dev/null \
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
  "$OPENCLAW" channels status --probe 2>/dev/null || true
fi

hr "Models (Auth + Routing)"
# Avoid leaking key material: use JSON output + jq redaction when available.
if have jq; then
  "$OPENCLAW" models status --json --probe --probe-max-tokens 16 2>/dev/null \
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
        elif type=="string" and test("(sk-or-v1|sk-|AIza|nvapi-)"; "i") then
          "<redacted>"
        else
          .
        end
      )' \
    | jq -r '.' || true
else
  echo "jq not found; skipping model auth details (avoid leaking key material)."
fi

hr "Recent Gateway Logs (tail 80)"
hr "Recent Gateway Logs (limit 80)"
"$OPENCLAW" logs --plain --limit 80 2>/dev/null || true
