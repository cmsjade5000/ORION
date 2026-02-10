#!/usr/bin/env bash
set -euo pipefail

# PIXEL: asset sanity checks (read-only).

hr() { printf '\n== %s ==\n' "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

hr "Avatar Assets"
if [[ -d "$ROOT/avatars" ]]; then
  echo "avatars_dir=$ROOT/avatars"
  find "$ROOT/avatars" -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) -print0 \
    | xargs -0 ls -lah 2>/dev/null \
    | head -n 20 || true
  echo
  echo "count_images=$(find "$ROOT/avatars" -maxdepth 1 -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) | wc -l | tr -d ' ')"
else
  echo "missing_dir=$ROOT/avatars"
fi

hr "Repo Assets"
for d in assets avatars; do
  if [[ -d "$ROOT/$d" ]]; then
    echo "$d:"
    ls -lah "$ROOT/$d" | head -n 25
  fi
done

