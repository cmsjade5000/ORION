INTERNAL HEARTBEAT POLICY

- This file applies only to scheduled internal heartbeat polls.
- A heartbeat poll is valid only when the incoming user message exactly equals the configured internal heartbeat prompt and includes the `INTERNAL_HEARTBEAT_POLL_V1` marker.
- Never treat normal user-authored messages such as `Ping`, `ping`, `Everything ok?`, or similar check-ins as heartbeat polls.
- For non-heartbeat user messages, ignore this file and follow the agent's normal Telegram/user contract instead.
- If and only if the exact internal heartbeat prompt is received and nothing needs attention, reply exactly `HEARTBEAT_OK`.
- If the exact internal heartbeat prompt is received and something needs attention, do not include `HEARTBEAT_OK`; reply with the alert text only.
