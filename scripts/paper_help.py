#!/usr/bin/env python3
"""
Emit a short paper-trading command list for Telegram/ORION.
"""

from __future__ import annotations

import json
import time


def main() -> int:
    msg = (
        "Paper trading commands\n"
        "/paper_help - show this list\n"
        "/paper_status - current paper status\n"
        "/paper_update - status + 8h digest\n"
        "/paper_update 24 - status + 24h digest"
    )
    print(
        json.dumps(
            {
                "mode": "paper_help",
                "timestamp_unix": int(time.time()),
                "message": msg,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
