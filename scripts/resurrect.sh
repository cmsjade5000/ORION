#!/usr/bin/env bash
set -e

# Check if OpenClaw gateway is running; start if not
echo "Checking if OpenClaw gateway is running..."
if ! pgrep -f 'openclaw gateway' >/dev/null; then
  echo "OpenClaw gateway not running. Starting..."
  openclaw gateway start
else
  echo "OpenClaw gateway is already running."
fi

# Wait a few seconds for the gateway to come up
echo "Waiting for gateway to become healthy..."
sleep 5

# Confirm status
echo "Checking gateway status..."
openclaw gateway status

# Send a Telegram notification of successful recovery
echo "Sending recovery message to Telegram..."
openclaw message send --to 8471523294 --message "🤖 ORION here: the server is back up and the gateway is running."

# Completion message
echo "Resurrect script complete."
