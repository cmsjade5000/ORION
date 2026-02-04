#!/usr/bin/env bash
set -euo pipefail

# Script: scan_repos_with_mino.sh
# Usage: scan_repos_with_mino.sh [--dry-run]

# Dry-run flag: if provided, script will only list repos and not call Mino or trigger audit
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "🔎 DRY RUN mode: no API calls or audits will be performed"
fi

set -euo pipefail

# Description: Clone or pull each configured repo and fetch metadata via Mino Web Agent.

CONFIG_FILE="$(dirname "$0")/../openclaw.yaml"

# Ensure yq is installed for YAML parsing
if ! command -v yq &>/dev/null; then
  echo "Error: yq is required but not found. Install yq to proceed." >&2
  exit 1
fi

# Determine state directory from config and initialize state file
state_dir=$(yq eval '.pulse.devAuditPipeline.stateDir // ".state"' "$CONFIG_FILE")
mkdir -p "$state_dir"
state_file="$state_dir/last_hashes.json"
if [ ! -f "$state_file" ]; then
  echo "{}" > "$state_file"
fi

# Ensure jq is installed for state management
if ! command -v jq &>/dev/null; then
  echo "Error: jq is required but not found. Install jq to proceed." >&2
  exit 1
fi

# Determine repos list from config
mapfile -t repos < <(yq eval '.pulse.repoMinoScan.repos[]' "$CONFIG_FILE")

if [ ${#repos[@]} -eq 0 ]; then
  echo "No repositories configured for repoMinoScan. Set pulse.repoMinoScan.repos in openclaw.yaml." >&2
  exit 1
fi

# Temporary workspace for cloning
WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

SUMMARY="📋 Mino Web Agent Repo Scan Summary — $(date -u)"
SUMMARY+=$'\n========================================\n'

# Loop and fetch with Mino for each repo
if $DRY_RUN; then
  echo "Configured repos:"; printf '%s
' "${repos[@]}";
  exit 0
fi
for repo in "${repos[@]}"; do
  echo "🔍 Scanning $repo"
  name=$(basename -s .git "$repo")
  echo "Cloning or updating $name..."
  dest="$WORKDIR/$name"
  if [ -d "$dest/.git" ]; then
    git -C "$dest" pull --ff-only
  else
    git clone "$repo" "$dest"
  fi

  # Check for repository changes
latest_hash=$(git -C "$dest" rev-parse HEAD)
prev_hash=$(jq -r --arg repo "$name" '.[$repo] // ""' "$state_file")
if [ "$latest_hash" = "$prev_hash" ]; then
  echo "⚡ Skipping $name: no new commits"
  rm -rf "$dest"
  continue
fi

echo "Fetching via Mino for $name"
  result=$(node -e "const { fetchWithMino } = require('../skills/mino-web-agent/manifest'); fetchWithMino('"$repo"','repo-info').catch(e => ({ error: e.message })); process.stdout.write(JSON.stringify({ repo: '"$name"', data: result }, null, 2));")
# Update state for $name
tmp_file="$state_file.tmp"
jq --arg repo "$name" --arg hash "$latest_hash" '.[$repo]=$hash' "$state_file" > "$tmp_file" && mv "$tmp_file" "$state_file"
  SUMMARY+=$"$result\n"
done

# Output consolidated summary
printf "%b" "$SUMMARY"

# Trigger the standalone skill-repo-audit workflow

echo "🔔 Triggering skill-repo-audit workflow..."
openclaw sessions send --label pulse --message "skill-repo-audit" || echo "⚠️ Failed to trigger skill-repo-audit"

printf "%b" "$SUMMARY"
