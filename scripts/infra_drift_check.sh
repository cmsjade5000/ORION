#!/usr/bin/env bash
set -euo pipefail

# Helper script to detect infrastructure drift via STRATUS skill
# Reads resource config from openclaw.yaml and runs detectDrift

CONFIG_FILE="$(dirname "$0")/../openclaw.yaml"

# Ensure yq is installed for YAML parsing
if ! command -v yq &>/dev/null; then
  echo "Error: yq is required but not found. Please install yq." >&2
  exit 1
fi

# Ensure openclaw CLI is available for stratus detectDrift
if ! command -v openclaw &>/dev/null; then
  echo "Error: openclaw CLI is required but not found." >&2
  exit 1
fi

# Read resources config (could be empty or JSON object)
resources=$(yq eval '.pulse.devAuditPipeline.drift.resources' "$CONFIG_FILE")

echo "🔍 Infrastructure Drift Check — $(date -u)"

# Run detectDrift and capture output (diff lines)
drift_output=$(openclaw stratus detectDrift --resources "$resources")

if [ -z "$drift_output" ]; then
  echo "✅ No infrastructure drift detected."
  exit 0
else
  echo "⚠️ Configuration drift detected:"
  echo "$drift_output"
  exit 1
fi
