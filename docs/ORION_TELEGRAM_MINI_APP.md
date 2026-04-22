# ORION Telegram Main Mini App

The ORION Telegram Mini App lives under:

- `apps/extensions/telegram/orion-miniapp/`

It is now a chat-first `Starship Console` surface for talking to ORION inside Telegram, with the inbox and today views available as secondary screens.

## What It Does

- `Chat`
  Real ORION turns inside the Mini App using the local guarded OpenClaw runtime path with stable session continuity.
- `Inbox`
  Actionable approvals plus delegated work highlights from `tasks/JOBS/summary.json`.
- `Today`
  Readable `today`, `followups`, and `review` snapshots from the existing assistant status scripts.

The Mini App intentionally reuses repo-native and runtime-native state instead of inventing a shadow system:

- `scripts/openclaw_guarded_turn.py`
- `scripts/assistant_status.py`
- `scripts/assistant_capture.py`
- `tasks/JOBS/summary.json`
- recent OpenClaw approval artifacts under `~/.openclaw/cron/runs/`

## Build And Run

Development/local launch:

```bash
npm run orion-miniapp
```

That command:

1. builds the React/Vite Mini App into `apps/extensions/telegram/orion-miniapp/public/`
2. starts the Node mini-app service

Build only:

```bash
npm run orion-miniapp:build
```

Start only with an already-built frontend:

```bash
npm run orion-miniapp:start
```

Default bind:

- `http://0.0.0.0:8787`

## Runtime Requirements

Required env:

- `ORION_TELEGRAM_BOT_TOKEN`
- `ORION_TELEGRAM_ALLOWED_USER_IDS` or `ORION_MINIAPP_OPERATOR_IDS`

Optional env:

- `ORION_MINIAPP_URL`
- `ORION_MINIAPP_SET_MENU_BUTTON=0|1`
- `ORION_MINIAPP_MAX_INIT_AGE_SECONDS`
- `ORION_WORKSPACE`

Current public entrypoint:

- `https://mac-mini.tail5e899c.ts.net`

## Telegram Launch

Bot surfaces:

- `/orion` sends a WebApp launch button
- `/agents` includes an `Open ORION` Mini App button
- plugin startup attempts to set the bot menu button to the Mini App URL

BotFather / Telegram setup:

1. Set the bot's **Main Mini App** URL to your deployed URL.
2. Keep the menu button pointed at the same Mini App.
3. Legacy deep links still work:
   - `https://t.me/<bot>?startapp=home`
   - `https://t.me/<bot>?startapp=approvals`
   - `https://t.me/<bot>?startapp=review`
4. New direct routes are also valid:
   - `https://t.me/<bot>?startapp=chat`
   - `https://t.me/<bot>?startapp=inbox`
   - `https://t.me/<bot>?startapp=today`

`home` now lands on the chat-first default surface.

## Chat Transport

The Mini App backend exposes:

- `POST /api/chat/runs`
- `GET /api/chat/runs/:id`
- `GET /api/chat/runs/:id/events`

Behavior:

- uses Telegram init-data auth plus the configured operator allowlist
- keeps a stable ORION session id per operator inside the Mini App
- runs turns through `scripts/openclaw_guarded_turn.py`
- streams staged run updates over SSE and then publishes the final assistant reply

This is a real ORION conversation surface. It does not send synthetic reply messages back into Telegram chat just to fake continuity.

## Inbox Behavior

Approvals:

- live approval prompts are still recovered from OpenClaw runtime artifacts
- when Telegram provides a live `query_id`, approval actions use `answerWebAppQuery`
- without a live `query_id`, the Mini App returns a manual Telegram command instead of pretending the action already happened

Delegated work:

- the inbox reads `tasks/JOBS/summary.json`
- actionable follow-up buttons route into the existing `assistant_capture.py` path
- the Mini App does not create or maintain a duplicate task database

## Public Exposure

This Mini App is no longer deployed on Fly.

The current production path is:

1. Telegram opens the public Tailscale Funnel URL
2. Tailscale Funnel forwards to the local Mini App on this machine
3. the local Mini App talks to the local ORION/OpenClaw runtime

Relevant local surfaces:

- `scripts/orion_miniapp_runner.sh`
- `scripts/orion_miniapp_launchagent.plist`

Operational note:

- if Telegram buttons stop working, verify `tailscale funnel status` and `curl https://mac-mini.tail5e899c.ts.net/readyz` before looking at ORION code
