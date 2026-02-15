#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys

# When executed as `python3 scripts/bankr_prompt.py`, sys.path[0] is the scripts/
# directory and the repo root may not be importable as a package. Fix up path.
try:
    from scripts.bankr_guard import classify_bankr_intent  # type: ignore
except ModuleNotFoundError:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.bankr_guard import classify_bankr_intent  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="bankr_prompt.py",
        description=(
            "Safe wrapper around `bankr prompt`.\n"
            "Defaults to read-only: blocks transaction/trading intents unless --allow-write is set."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("text", nargs="+", help="Prompt text to send to Bankr.")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Allow prompts that look like signing/submitting txs, swapping, bridging, etc.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Optional: path to Bankr CLI config.json (passed through to `bankr --config`).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Fail if `bankr prompt` takes longer than this many seconds (default: 180).",
    )
    parser.add_argument(
        "--",
        dest="passthrough",
        nargs=argparse.REMAINDER,
        help="Pass remaining args through to `bankr prompt` (advanced).",
    )

    args = parser.parse_args()
    text = " ".join(args.text).strip()
    if not text:
        print("ERROR: Empty prompt.", file=sys.stderr)
        return 2

    intent = classify_bankr_intent(text)
    if intent.is_write and not args.allow_write:
        hits = ", ".join(intent.hits[:6])
        print(
            "REFUSED: This prompt looks like it requests on-chain actions (write intent).\n"
            f"Matched: {hits}\n"
            "Re-run with --allow-write only after explicit user confirmation.",
            file=sys.stderr,
        )
        return 3

    cmd = ["bankr"]
    if args.config:
        cmd.extend(["--config", args.config])
    cmd.extend(["prompt", text])

    # Append passthrough args after the prompt text (rare).
    # This matches Bankr CLI calling pattern: `bankr prompt [options] [text...]`.
    if args.passthrough:
        cmd.extend(args.passthrough)

    # Ensure we don't accidentally leak env in debug output.
    env = os.environ.copy()

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=False,
            timeout=max(1, int(args.timeout_seconds)),
        )
        return int(proc.returncode)
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: Timed out after {args.timeout_seconds}s waiting for Bankr.\n"
            "If Bankr printed a Job ID above, you can check it with: bankr status <jobId>",
            file=sys.stderr,
        )
        return 5
    except FileNotFoundError:
        print(
            "ERROR: `bankr` CLI not found in PATH.\n"
            "Install: npm install -g @bankr/cli\n"
            "Then: bankr login",
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
