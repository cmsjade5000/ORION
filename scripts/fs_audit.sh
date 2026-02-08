#!/usr/bin/env bash
set -euo pipefail

# Lightweight filesystem audit helpers (safe, read-only).
#
# Prints repo size, largest files, and large OpenClaw logs for quick triage.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

hr() { printf '\n== %s ==\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

hr "Repo Size"
du -sh "$ROOT" 2>/dev/null || true

hr "Largest Files (Repo, top 20)"
python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ.get("ROOT", ".")).resolve()

items = []
for p in root.rglob("*"):
    if not p.is_file():
        continue
    # Skip git + node_modules style noise.
    s = str(p)
    if "/.git/" in s or "/node_modules/" in s:
        continue
    try:
        sz = p.stat().st_size
    except OSError:
        continue
    items.append((sz, p))

items.sort(reverse=True, key=lambda x: x[0])
for sz, p in items[:20]:
    rel = p.relative_to(root)
    print(f"{sz:>12}  {rel}")
PY

hr "OpenClaw Logs (Large Files > 5MB)"
LOG_DIR="$HOME/.openclaw/logs"
if [ -d "$LOG_DIR" ]; then
  python3 - <<'PY'
import os
from pathlib import Path

log_dir = Path(os.path.expanduser("~/.openclaw/logs"))
threshold = 5 * 1024 * 1024
rows = []
for p in log_dir.glob("**/*"):
    if not p.is_file():
        continue
    try:
        sz = p.stat().st_size
    except OSError:
        continue
    if sz >= threshold:
        rows.append((sz, p))
rows.sort(reverse=True, key=lambda x: x[0])
for sz, p in rows[:30]:
    print(f"{sz:>12}  {p}")
PY
else
  printf 'no local openclaw logs dir: %s\n' "$LOG_DIR"
fi

