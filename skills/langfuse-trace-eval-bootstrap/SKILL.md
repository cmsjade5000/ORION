---
name: langfuse-trace-eval-bootstrap
description: Bootstrap Langfuse tracing/eval scaffolding for ORION workflows with reproducible local setup.
metadata:
  invocation: user
---

# Langfuse Trace Eval Bootstrap

Use this skill to scaffold a minimal Langfuse tracing/eval setup for ORION workflows and verify trace ingestion with a local smoke script.

## Purpose

- Bootstrap a repeatable local project layout for Langfuse tracing/eval experiments.
- Provide starter files for environment configuration and smoke verification.
- Validate end-to-end trace/span ingestion with explicit `flush()`.

## Prerequisites

- Python 3.9+ available (default command is `python3`).
- Langfuse project credentials:
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_SECRET_KEY`
- Optional `LANGFUSE_BASE_URL` (defaults to `https://cloud.langfuse.com`).
- Network access for dependency install and smoke submission.

## One-command helper

```bash
bash skills/langfuse-trace-eval-bootstrap/scripts/bootstrap_langfuse_trace_eval.sh
```

## Install + run example

```bash
bash skills/langfuse-trace-eval-bootstrap/scripts/bootstrap_langfuse_trace_eval.sh \
  --project-dir .tmp/langfuse-bootstrap \
  --install \
  --run-smoke
```

## Expected outcomes

- `<project-dir>/.env.example` exists with required variables.
- `<project-dir>/langfuse_smoke.py` exists and can run locally.
- `<project-dir>/requirements.txt` exists with Langfuse bootstrap dependencies.
- If `--install` is used, `<project-dir>/.venv` exists with dependencies installed.
- If `--run-smoke` is used with valid credentials, a trace ID and trace URL are printed.

## Failure triage

- Missing credentials: export keys or copy `.env.example` to `.env` and fill values.
- Import errors: re-run with `--install` or install from `requirements.txt` manually.
- No traces in UI: confirm `LANGFUSE_BASE_URL` region/host and re-run smoke.
- Network/auth issues: verify key validity in the target Langfuse project and retry.
