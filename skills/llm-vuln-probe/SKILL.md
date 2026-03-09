---
name: llm-vuln-probe
description: Run focused garak vulnerability probes against target LLMs for jailbreak, injection, and unsafe-output risk.
metadata:
  invocation: user
---

# LLM Vuln Probe

Use this skill to run repeatable NVIDIA garak probes against a target model and quickly check common risk areas, including prompt injection, encoding bypasses, and DAN-style jailbreak patterns.

## Purpose

- Run focused vulnerability checks on a chosen target model with a known probe set.
- Keep invocation consistent across local runs and CI jobs.
- Support safe preflight with dry-run and probe-discovery workflows.

## Prerequisites

- Python 3.9+ available (default command is `python3`).
- Network access for provider calls and package install when using `--install`.
- Target provider credentials configured in environment.

OpenAI note:
- For `--target-type openai`, `OPENAI_API_KEY` must be set unless using `--dry-run` or `--list-probes`.

## One-Command Helper

```bash
bash skills/llm-vuln-probe/scripts/run_garak_probe.sh
```

## Dry-Run Example

```bash
bash skills/llm-vuln-probe/scripts/run_garak_probe.sh --dry-run
```

## List Probes Example

```bash
bash skills/llm-vuln-probe/scripts/run_garak_probe.sh --list-probes
```

## Custom Target Example

```bash
bash skills/llm-vuln-probe/scripts/run_garak_probe.sh \
  --target-type openai \
  --target-name gpt-5-nano \
  --probes encoding,promptinject,dan
```
