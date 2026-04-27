#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

# Keep LaunchAgent environment explicit.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/Users/corystoner/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

log_prefix() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

main() {
  local branch
  local has_changes
  local commit_message

  branch="$(git rev-parse --abbrev-ref HEAD)"
  commit_message="chore(yeet): automated cleanup $(date -u '+%Y-%m-%d %H:%M:%SZ')"

  echo "[$(log_prefix)] Starting yeet scheduler run on branch: ${branch}"

  has_changes="$(git status --porcelain=v1)"

  if [[ -n "${has_changes}" ]]; then
    echo "[$(log_prefix)] Found local changes; committing."
    git add -A
    git commit -m "${commit_message}"

    if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
      if git push; then
        echo "[$(log_prefix)] Push succeeded."
      else
        echo "[$(log_prefix)] Push failed; continuing to prune." >&2
      fi
    else
      echo "[$(log_prefix)] No upstream branch configured; skipping push."
    fi
  else
    echo "[$(log_prefix)] No tracked changes detected; nothing to commit."
  fi

  echo "[$(log_prefix)] Running worktree prune cycle."
  git clean -fdx
  git remote prune origin
  git prune --expire now
  git gc --prune=now

  echo "[$(log_prefix)] Yeet run completed."
}

main "$@"
