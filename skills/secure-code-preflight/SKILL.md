---
name: secure-code-preflight
description: Run Semgrep security preflight checks with ORION-focused defaults before merge or deploy.
metadata:
  invocation: user
---

# Secure Code Preflight

Run a Semgrep security gate quickly before merge or deploy.

## Purpose

- Catch common security issues early with a repeatable local check.
- Apply baseline Semgrep security rules plus ORION-specific shell injection checks.
- Fail the run on findings at or above a selected severity.

## Prerequisites

- Run from repo root.
- Semgrep installed (`semgrep` in PATH), or Python module fallback available.
- Optional: network access for remote registry config `p/security-audit`.

## One-Command Helper

```bash
bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh
```

## Example Commands

```bash
# Show effective command without scanning
bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh --dry-run

# Scan a custom target directory
bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh --target src

# Export JSON findings for CI/reporting
bash skills/secure-code-preflight/scripts/run_secure_code_preflight.sh \
  --severity WARNING \
  --json-output .tmp/secure-preflight.json
```

## Interpretation And Next Actions

- Exit `0`: no findings at or above chosen severity.
- Exit `1`: findings detected; fix and rerun before merge/deploy.
- Exit `2`: bad arguments or invalid usage; correct command options.
- Exit `127`: Semgrep unavailable; install it, then rerun.

