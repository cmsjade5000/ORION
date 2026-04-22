# ORION Start Here

This is the first-page onboarding path for a new maintainer or operator.

## Read First

- [agents/ORION/SOUL.md](/Users/corystoner/src/ORION/agents/ORION/SOUL.md)
- [docs/TASK_PACKET.md](/Users/corystoner/src/ORION/docs/TASK_PACKET.md)
- [docs/NATIVE_SUBAGENT_CONTROL_PLANE.md](/Users/corystoner/src/ORION/docs/NATIVE_SUBAGENT_CONTROL_PLANE.md)
- [docs/FOLLOW_THROUGH.md](/Users/corystoner/src/ORION/docs/FOLLOW_THROUGH.md)
- [docs/ORION_SINGLE_BOT_ORCHESTRATION.md](/Users/corystoner/src/ORION/docs/ORION_SINGLE_BOT_ORCHESTRATION.md)

## Bootstrap Checks

Run these in order for a fresh local checkout or a runtime refresh:

```bash
openclaw config validate --json
make soul
openclaw gateway install
openclaw gateway start
openclaw doctor --repair
openclaw channels status --probe
make inbox-cycle
```

## Contract Checks

Run these after instruction or delegation changes:

```bash
python3 -m unittest \
  tests.test_orion_instruction_contracts \
  tests.test_instruction_duplicate_allowlist \
  tests.test_delegated_job_state \
  tests.test_openclaw_workspace_contract
```

## Where To Go Next

- [README.md](/Users/corystoner/src/ORION/README.md)
- [docs/WORKFLOW.md](/Users/corystoner/src/ORION/docs/WORKFLOW.md)
- [docs/ORION_EXTENSION_SURFACES.md](/Users/corystoner/src/ORION/docs/ORION_EXTENSION_SURFACES.md)
- [docs/TELEGRAM_AGENT_CHAT_RULES.md](/Users/corystoner/src/ORION/docs/TELEGRAM_AGENT_CHAT_RULES.md)
