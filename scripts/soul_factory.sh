#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"
CORE_DIR="$SRC_DIR/core"
SHARED_DIR="$CORE_DIR/shared"
ROLES_DIR="$SRC_DIR/agents"
AGENTS_DIR="$ROOT_DIR/agents"
USER_MD="$ROOT_DIR/USER.md"

# Ordered shared layers (edit order here if you ever change it)
SHARED_LAYERS=(
  "CONSTITUTION.md"
  "USER.md"
  "FOUNDATION.md"
  "ROUTING.md"
)

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Missing required file: $path" >&2
    exit 1
  fi
}

build_agent() {
  local agent="$1"
  local role_file="$ROLES_DIR/${agent}.md"
  local out_dir="$AGENTS_DIR/${agent}"
  local out_file="$out_dir/SOUL.md"

  mkdir -p "$out_dir"

  require_file "$role_file"
  for f in "${SHARED_LAYERS[@]}"; do
    if [[ "$f" == "USER.md" ]]; then
      require_file "$USER_MD"
    else
      require_file "$SHARED_DIR/$f"
    fi
  done

  {
    echo "# SOUL.md — ${agent}"
    echo
    echo "**Generated:** $(timestamp)"
    echo "**Source:** src/core/shared + USER.md + src/agents/${agent}.md"
    echo
    echo "---"
    echo
    # Shared layers
    for f in "${SHARED_LAYERS[@]}"; do
      echo "<!-- BEGIN shared/${f} -->"
      if [[ "$f" == "USER.md" ]]; then
        cat "$USER_MD"
      else
        cat "$SHARED_DIR/$f"
      fi
      echo
      echo "<!-- END shared/${f} -->"
      echo
      echo "---"
      echo
    done
    # Role layer
    echo "<!-- BEGIN roles/${agent}.md -->"
    cat "$role_file"
    echo
    echo "<!-- END roles/${agent}.md -->"
    echo
  } > "$out_file"

  echo "✅ Built $out_file"
}

main() {
  local agents=()
  if [[ "${1-}" == "--all" || "${#}" -eq 0 ]]; then
    # Build for every role file present
    while IFS= read -r -d '' f; do
      agents+=("$(basename "$f" .md)")
    done < <(find "$ROLES_DIR" -maxdepth 1 -type f -name "*.md" -print0 | sort -z)
  else
    agents=("$@")
  fi

  if [[ "${#agents[@]}" -eq 0 ]]; then
    echo "No agents found in $ROLES_DIR" >&2
    exit 1
  fi

  for a in "${agents[@]}"; do
    build_agent "$a"
  done
}

main "$@"
