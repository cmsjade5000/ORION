#!/usr/bin/env bash
set -euo pipefail

# Helper script to perform security audits on skill repositories
# Reads list of repos from openclaw.yaml or from command-line arguments if provided.

# Location of openclaw config (relative to repo root)
CONFIG_FILE="$(dirname "$0")/../openclaw.yaml"

# Ensure yq is installed for YAML parsing
if ! command -v yq &>/dev/null; then
  echo "Error: yq is required but not found. Please install yq." >&2
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

# Determine repositories to audit: args override config
if [ "$#" -gt 0 ]; then
  repos=("$@")
else
  mapfile -t repos < <(yq eval '.pulse.skillRepoAudit.repos[]' "$CONFIG_FILE")
fi

if [ ${#repos[@]} -eq 0 ]; then
  echo "No repositories configured for skillRepoAudit. Set pulse.skillRepoAudit.repos in openclaw.yaml." >&2
  exit 1
fi

# Create workspace for cloning
WORKDIR=$(mktemp -d)
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

SUMMARY="Security Audit Summary - $(date -u)"
SUMMARY+=$'\n========================================\n'

# Loop over repos and run audits
for repo in "${repos[@]}"; do
  echo "Processing $repo..."
  name=$(basename -s .git "$repo")
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
    git -C "$dest" pull --ff-only
  else
    git clone "$repo" "$dest"
  fi
  SUMMARY+=$"--- $name ---\n"
  # Run deep security audit
  openclaw security audit --deep --repo "$dest" >> "$WORKDIR/${name}_audit.log" 2>&1
  SUMMARY+=$(cat "$WORKDIR/${name}_audit.log")
  SUMMARY+=$'\n'
  SUMMARY+=$'\n'

  # Update state for $name
tmp_file="$state_file.tmp"
jq --arg repo "$name" --arg hash "$latest_hash" '.[$repo]=$hash' "$state_file" > "$tmp_file" && mv "$tmp_file" "$state_file"

# Clean up repo clone to save space
  rm -rf "$dest"
done

# Output consolidated summary
printf "%b" "$SUMMARY"
