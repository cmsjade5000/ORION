#!/usr/bin/env python3
"""Minimal Langfuse trace/span smoke test with explicit flush."""

import os

from dotenv import load_dotenv
from langfuse import Langfuse

DEFAULT_BASE_URL = "https://cloud.langfuse.com"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    load_dotenv()

    public_key = required_env("LANGFUSE_PUBLIC_KEY")
    secret_key = required_env("LANGFUSE_SECRET_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL

    langfuse = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
    )

    trace_id = langfuse.create_trace_id()

    with langfuse.start_as_current_observation(
        name="orion-langfuse-smoke",
        as_type="span",
        trace_context={"trace_id": trace_id},
        input={"workflow": "orion", "mode": "smoke"},
    ) as root:
        root.update(metadata={"component": "langfuse-trace-eval-bootstrap"})

        with root.start_as_current_observation(name="child-operation") as child:
            child.update(output={"status": "ok"})

        root.update(output={"result": "smoke-complete"})

    langfuse.create_score(
        name="bootstrap_smoke_score",
        value=1.0,
        trace_id=trace_id,
        data_type="NUMERIC",
        comment="Smoke trace emitted successfully",
    )

    langfuse.flush()

    trace_url = langfuse.get_trace_url(trace_id=trace_id)
    print("Langfuse smoke trace flushed.")
    print(f"Trace ID: {trace_id}")
    if trace_url:
        print(f"Trace URL: {trace_url}")


if __name__ == "__main__":
    main()
