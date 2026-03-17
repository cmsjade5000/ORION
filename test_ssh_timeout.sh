#!/usr/bin/env bash
set -euo pipefail

run_with_timeout() {
  local timeout_sec="${1:-30}"
  shift
  local cmd=("$@")
  
  # Run the command in background
  "${cmd[@]}" &
  local cmd_pid=$!
  
  # Timer to kill after timeout
  (
    sleep "$timeout_sec"
    if kill -0 "$cmd_pid" 2>/dev/null; then
      echo "run_with_timeout: killing ${cmd[*]} after ${timeout_sec}s" >&2
      kill -TERM "$cmd_pid" 2>/dev/null || kill -KILL "$cmd_pid" 2>/dev/null
    fi
  ) &
  local timer_pid=$!
  
  # Wait for command to finish
  wait "$cmd_pid" 2>/dev/null
  local exit_code=$?
  
  # Cleanup timer
  kill -TERM "$timer_pid" 2>/dev/null || true
  wait "$timer_pid" 2>/dev/null || true
  
  return $exit_code
}

run_with_timeout 5 ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new root@100.75.104.54 'echo "test"'
echo "Exit: $?"
