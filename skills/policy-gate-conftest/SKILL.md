---
name: policy-gate-conftest
description: Enforce ORION policy-as-code gates on structured artifacts using Conftest and Rego.
metadata:
  invocation: user
---

# Policy Gate Conftest

Use Conftest plus Rego policies to enforce policy-as-code gates on ORION artifacts such as `task_packet_v1` JSON payloads.

## Prerequisites

- `conftest` installed and available on `PATH`.
- Run commands from repo root: `/Users/corystoner/src/ORION`.

## One-Command Helper

```bash
bash skills/policy-gate-conftest/scripts/run_policy_gate.sh
```

## Sample Pass/Fail Commands

```bash
# Expected pass
bash skills/policy-gate-conftest/scripts/run_policy_gate.sh \
  skills/policy-gate-conftest/examples/task_packet.pass.json

# Expected fail
bash skills/policy-gate-conftest/scripts/run_policy_gate.sh \
  skills/policy-gate-conftest/examples/task_packet.fail.json
```

## What To Do On Failures

- Read deny messages to identify missing or empty required fields.
- Update the artifact to include non-empty `owner`, `requester`, `objective`, `success_criteria`, and `stop_gates`.
- Re-run the helper script until the check passes.
