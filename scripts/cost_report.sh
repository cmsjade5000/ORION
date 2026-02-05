#!/usr/bin/env bash
set -euo pipefail

# Helper script to generate LLM cost and token usage report
# Reads cost thresholds from openclaw.yaml and runs the model-usage skill

CONFIG_FILE="$(dirname "$0")/../openclaw.yaml"

# Ensure yq is installed for YAML parsing
if ! command -v yq &>/dev/null; then
  echo "Error: yq is required but not found. Please install yq." >&2
  exit 1
fi

# Ensure openclaw CLI is available for model-usage skill
if ! command -v openclaw &>/dev/null; then
  echo "Error: openclaw CLI is required but not found." >&2
  exit 1
fi

# Read cost thresholds from config (in USD)
warning_threshold=$(yq eval '.pulse.devAuditPipeline.cost.warningThreshold' "$CONFIG_FILE")
alert_threshold=$(yq eval '.pulse.devAuditPipeline.cost.alertThreshold' "$CONFIG_FILE")

# Header
echo "📊 LLM Cost Report — $(date -u)"
echo "Thresholds: warning=\$$warning_threshold, alert=\$$alert_threshold"
echo ""

# Run the model-usage skill to get per-model cost breakdown
usage_summary=$(openclaw model-usage --mode all --format text)
echo "$usage_summary"

# Extract total cost from summary (expects a line with "Total Cost: $<value>")
total_cost=$(echo "$usage_summary" | awk '/Total/{print $NF}' | tr -d '$')

# Compare against thresholds (requires bc for floating-point comparison)
if (( $(echo "$total_cost > $alert_threshold" | bc -l) )); then
  echo ""
  echo "🚨 Cost above alert threshold: $total_cost > $alert_threshold"
  exit 1
elif (( $(echo "$total_cost > $warning_threshold" | bc -l) )); then
  echo ""
  echo "⚠️ Cost above warning threshold: $total_cost > $warning_threshold"
  exit 0
else
  echo ""
  echo "✅ Cost within threshold."
  exit 0
fi
