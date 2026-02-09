#!/usr/bin/env bash
set -euo pipefail

echo "== ORION Resurrection (macOS) =="

echo "-> Restarting OpenClaw gateway..."
if ! openclaw gateway restart; then
  echo "-> Restart failed; ensuring service is installed..."
  openclaw gateway install
  echo "-> Starting OpenClaw gateway..."
  openclaw gateway start
fi

echo "-> Running health and security checks..."
openclaw doctor --repair
openclaw security audit --deep
openclaw channels status --probe

echo "-> Verifying agent bindings and model status..."
openclaw agents list --bindings
openclaw models status

echo "== Done =="
