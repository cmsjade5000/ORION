---
name: ci-failure-triage
description: STRATUS-focused CI failure triage for GitHub Actions using gh (read-only), plus a small categorizer script.
metadata:
  invocation: user
---

# CI Failure Triage (STRATUS)

Use this skill when GitHub Actions checks fail and you need a fast, repeatable triage output suitable for a Task Packet `Result:`.

## Requirements

- `gh` CLI installed
- `gh auth status` shows authenticated

## Quick Triage (Failed Steps Only)

```bash
gh run view <run-id-or-url> --log-failed
```

## Categorized Triage (Recommended)

```bash
python3 scripts/ci_triage.py <run-id-or-url>
```

If you need an explicit repo:

```bash
python3 scripts/ci_triage.py <run-id> --repo owner/repo
```

## Output Expectations

The script outputs:
- `CATEGORY: ...` (deps/import, tests, typecheck, node-build, auth/permissions, network/timeout, resources, unknown)
- `SIGNALS:` (up to 6 lines)
- `NEXT:` (2-4 concrete next steps)

## Safety

Read-only only. Do not re-run workflows or merge PRs without explicit authorization.

