# Working Memory

## Current Task

Address smoke test failures for linting, JS/TS tests, Node workingMemory check, and OpenRouter config lookup.

## Status

Discovered that:
- Linting fails due to missing pre‑commit
- JS/TS tests fail (no package.json)
- Node workingMemory check errors (module path incorrect)
- OpenRouter entry not detected in config via CLI

## Next Steps

1. Install/configure pre‑commit or adjust the `make lint` target.
2. Add or remove `package.json` and update JS/TS test commands.
3. Fix the module import path for `src/core` in the Node check.
4. Verify and reload the OpenRouter config entry (`openclaw gateway config.patch`).
5. Update the Node smoke-test import path for `workingMemory` once the smoke-test script location is identified.
5. Re-run the full smoke test to confirm all fixes.
