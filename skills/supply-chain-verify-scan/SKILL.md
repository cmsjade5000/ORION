---
name: supply-chain-verify-scan
description: Verify artifact signatures with Cosign and gate vulnerabilities with Grype before deploy.
metadata:
  invocation: user
---

# Supply Chain Verify Scan

Use this skill to enforce a pre-deploy gate with two checks:

- Verify artifact signatures with Cosign.
- Gate deployment on Grype vulnerability severity.

## Purpose

- Prevent unsigned or untrusted artifacts from moving to deploy.
- Block artifacts with vulnerabilities at or above your chosen threshold.
- Produce a repeatable local/CI command for supply chain checks.

## Prerequisites

- `cosign` installed and in PATH (unless using `--skip-cosign`).
- `grype` installed and in PATH (unless using `--skip-grype`).
- A scan target accepted by Grype (`image`, filesystem path, or `sbom:...`).
- For Cosign verification, either a public key (`--cosign-key`) or keyless identity+issuer pair.

## One-Command Helper

```bash
bash skills/supply-chain-verify-scan/scripts/run_supply_chain_gate.sh \
  --target ghcr.io/example/app:1.2.3 \
  --cosign-key ./cosign.pub
```

## Key-Based Example

```bash
bash skills/supply-chain-verify-scan/scripts/run_supply_chain_gate.sh \
  --target ghcr.io/example/app:1.2.3 \
  --cosign-key ./cosign.pub \
  --fail-on high
```

## Keyless Example

```bash
bash skills/supply-chain-verify-scan/scripts/run_supply_chain_gate.sh \
  --target ghcr.io/example/app:1.2.3 \
  --certificate-identity "https://github.com/example/repo/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --fail-on high
```

## Interpreting Failures

- Exit `0`: enabled checks passed.
- Exit `1`: verification or scan gate failed.
- Exit `2`: invalid arguments or missing required verification inputs.
- Exit `127`: required command missing (`cosign` or `grype`).

When the gate fails, fix signature trust or vulnerabilities, then rerun before deploy.
