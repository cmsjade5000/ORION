#!/usr/bin/env bash
set -euo pipefail

# Poll GitHub PRs and create lightweight Task Packets under tasks/PR/.
# Intended to be safe: no merges, no checkouts, no side effects beyond files.

REPO="${REPO:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="${STATE_FILE:-$ROOT/tmp/pr_poll_state.json}"
OUT_DIR="${OUT_DIR:-$ROOT/tasks/PR}"

usage() {
  cat <<'USAGE'
Usage:
  REPO=cmsjade5000/ORION ./scripts/pr_poll.sh

Env:
  REPO        GitHub repo (owner/name). If unset, derived from git remote origin.
  STATE_FILE  Poll state JSON path (default: tmp/pr_poll_state.json)
  OUT_DIR     Output folder for PR task packets (default: tasks/PR)
USAGE
}

have() { command -v "$1" >/dev/null 2>&1; }

if ! have gh; then
  echo "ERROR: gh CLI not found" >&2
  exit 1
fi
if ! have jq; then
  echo "ERROR: jq not found" >&2
  exit 1
fi

cd "$ROOT"

if [ -z "$REPO" ]; then
  if have git; then
    origin="$(git remote get-url origin 2>/dev/null || true)"
    # Supports git@github.com:owner/repo.git and https://github.com/owner/repo(.git)
    REPO="$(printf '%s' "$origin" | sed -E 's#^(git@github.com:|https://github.com/)##; s#\\.git$##')"
  fi
fi

if [ -z "$REPO" ] || ! printf '%s' "$REPO" | grep -Eq '^[^/]+/[^/]+$'; then
  usage >&2
  echo "ERROR: REPO is required (example: cmsjade5000/ORION)" >&2
  exit 2
fi

mkdir -p "$OUT_DIR" "$(dirname "$STATE_FILE")"

if [ ! -f "$STATE_FILE" ]; then
  printf '%s\n' '{"seen":{}}' >"$STATE_FILE"
fi

prs_json="$(gh pr list --repo "$REPO" --state open --limit 50 --json number,title,author,updatedAt,url,headRefName,baseRefName,isDraft,labels)"

new_count=0
changed_count=0

echo "$prs_json" | jq -c '.[]' | while read -r pr; do
  num="$(echo "$pr" | jq -r '.number')"
  title="$(echo "$pr" | jq -r '.title')"
  url="$(echo "$pr" | jq -r '.url')"
  author="$(echo "$pr" | jq -r '.author.login')"
  updated="$(echo "$pr" | jq -r '.updatedAt')"
  head="$(echo "$pr" | jq -r '.headRefName')"
  base="$(echo "$pr" | jq -r '.baseRefName')"
  draft="$(echo "$pr" | jq -r '.isDraft')"
  labels="$(echo "$pr" | jq -r '[.labels[].name] | join(", ")')"

  last="$(jq -r --arg n "$num" '.seen[$n] // empty' "$STATE_FILE")"
  out="$OUT_DIR/PR-$num.md"

  if [ -z "$last" ]; then
    new_count=$((new_count+1))
  elif [ "$last" != "$updated" ]; then
    changed_count=$((changed_count+1))
  fi

  if [ -z "$last" ] || [ "$last" != "$updated" ] || [ ! -f "$out" ]; then
    cat >"$out" <<EOF
# Task Packet (PR Review)

Task: Review PR #$num ($title)
Repo: $REPO
URL: $url
Author: $author
Branch: $head -> $base
Draft: $draft
Labels: ${labels:-none}
Updated: $updated

Deliverable:
- Review summary (risks, behavior changes, missing tests)
- Suggested edits (if any)
- Merge recommendation

Merge policy:
- Do NOT merge unless Cory explicitly approves, or PR has label: orion-automerge
EOF
  fi

  tmp="$(mktemp)"
  jq --arg n "$num" --arg updated "$updated" '.seen[$n]=$updated' "$STATE_FILE" >"$tmp"
  mv "$tmp" "$STATE_FILE"
done

printf 'PR poll complete for %s\n' "$REPO"
printf 'State: %s\n' "$STATE_FILE"
printf 'Output: %s\n' "$OUT_DIR"
