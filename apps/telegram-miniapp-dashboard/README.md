# ORION Telegram Mini App: Network Dashboard (Starter)

This is a starter scaffold for a **Telegram Mini App** that opens from ORION’s bot and renders a live network dashboard.

## What’s Included

- React + Vite app, mobile-first layout
- Telegram WebApp SDK integration (reads `Telegram.WebApp.initData` when available)
- Network UI
  - Central `ORION` node
  - Orbiting sub-agent nodes: `ATLAS`, `EMBER`, `PIXEL`, `NODE`, `LEDGER`, `AEGIS`
  - Animated connection line `ORION -> active agent` (placeholder)
  - Placeholder node pulse animation
  - Command bar UI (placeholder)
- Express backend
  - `GET /api/state` mock live state
  - `POST /api/sse-auth` + `GET /api/events` SSE stream (push updates)
  - `POST /api/ingest` ORION -> Mini App event ingest (rebroadcasts over SSE)
- `POST /api/command` command ingestion (`202 accepted`, optional OpenClaw routing)
  - Serves `dist/` in production

## SSE Event Types (v0)

The SSE endpoint (`GET /api/events`) emits:

- `state`: periodic full snapshot (recovery + UI render source of truth)
- `artifact.created` (optional): a file/export was generated and is available to download
- `agent.activity`
- `tool.started`, `tool.finished`, `tool.failed`
- `task.created`, `task.routed`, `task.started`, `task.completed`, `task.failed`

Notes:
- The server will also emit some extra convenience events (for example `command.accepted`) during development.
- `state` frames are the authoritative UI state; the fine-grained events exist for low-latency UX and future replay/debugging.
- Dev convenience: when `/api/command` is running in simulated mode (OpenClaw routing disabled), the server can generate preview artifacts/replies for local testing.
  - In production, preview artifacts/replies are disabled by default to avoid fake outputs.
  - Override with `PREVIEW_ARTIFACTS_ENABLED=1` and/or `PREVIEW_RESPONSES_ENABLED=1` if you intentionally want demo behavior.

## ORION -> Mini App Ingest (v0)

ORION (or a bridge) POSTs events to `POST /api/ingest`.

Auth:
- `Authorization: Bearer $INGEST_TOKEN`

Environment:
- `INGEST_TOKEN`: shared secret for service-to-service auth (set as a Fly secret)
- `MOCK_STATE`: default `0` (off). Set to `1` to enable mock motion when ORION ingest isn't wired yet.

### Wiring From The Gateway Packet Runner / Notifier

This repo includes two helper scripts that can emit real `task.*`, `tool.*`, and `response.created` events:

- `/Users/corystoner/src/ORION/scripts/run_inbox_packets.py`
- `/Users/corystoner/src/ORION/scripts/notify_inbox_results.py`

Configure either environment variables or `~/.openclaw/openclaw.json` `env.vars`:

- `MINIAPP_INGEST_URL`: base URL (example `https://<your-miniapp-host>` or `http://127.0.0.1:8787`)
- `MINIAPP_INGEST_TOKEN`: token (should match the server’s `INGEST_TOKEN`)

Example payloads:

```json
{ "type": "agent.activity", "agentId": "ATLAS", "activity": "search", "ts": 1739068800000 }
```

```json
{ "type": "response.created", "agentId": "ORION", "text": "Short reply for the user.", "ts": 1739068800345 }
```

```json
{
  "type": "artifact.created",
  "agentId": "LEDGER",
  "artifact": {
    "id": "art_123",
    "kind": "file",
    "name": "xyz.pdf",
    "mime": "application/pdf",
    "url": "https://example.com/xyz.pdf",
    "createdAt": 1739068800789,
    "sizeBytes": 192031
  }
}
```

```json
{ "type": "tool.started", "agentId": "PIXEL", "tool": { "name": "web.run" }, "ts": 1739068800123 }
```

```json
{ "type": "task.routed", "agentId": "EMBER", "task": { "id": "tp_123" }, "ts": 1739068800456 }
```

Optional (future): full snapshots:

```json
{ "type": "state", "state": { "ts": 1739068800000, "activeAgentId": null, "agents": [], "orion": { "status": "idle", "processes": ["🧭"] } } }
```

## Artifact Upload (v0)

If ORION generates a file locally and wants the Mini App to serve it (so users can tap a bubble and download), upload it to:

- `POST /api/artifacts`

Auth:
- `Authorization: Bearer $INGEST_TOKEN`

Headers:
- `Content-Type`: the MIME type (example `application/pdf`)
- `x-artifact-name`: download filename (example `xyz.pdf`)
- `x-agent-id` (optional): which agent produced it (example `LEDGER`)

Body:
- raw bytes of the file

Response:
- `{ ok: true, artifact: { id, url, ... } }`

Notes:
- The server stores artifacts in an ephemeral directory by default (`/tmp/...`), controlled by `ARTIFACTS_DIR`.
- Downloads are authorized via the same short-lived signed token used for SSE; the frontend appends `?token=...` automatically.

## Local Dev

From this folder:

```bash
npm install
npm run dev
```

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8787/api/state`
- SSE: `http://127.0.0.1:8787/api/events` (EventSource uses a short-lived token from `/api/sse-auth`)

Note: opening the app in a normal browser will show `No Telegram initData` (expected). In Telegram it will populate.

## Security: Telegram `initData` Verification

The backend verifies `x-telegram-init-data` (signature + age) when present.

Environment:
- `TELEGRAM_BOT_TOKEN`: bot token used to verify `initData` (preferred for local dev)
- `TELEGRAM_BOT_TOKEN_FILE` (or `TELEGRAM_TOKEN_FILE`): path to a token file
- `TELEGRAM_INITDATA_MAX_AGE_SEC`: default `86400` (24h)
- `TELEGRAM_INITDATA_CLOCK_SKEW_SEC`: default `60` (tolerate minor clock skew)
- `ALLOW_UNVERIFIED_INITDATA=1`: dev escape hatch (allows `/api/command` without verification)

## Optional: Route Commands Into ORION (OpenClaw)

If this server runs on the same machine as OpenClaw, you can have `/api/command` invoke ORION:

- `OPENCLAW_ROUTE_COMMANDS=1`
- `OPENCLAW_AGENT_ID=main` (default `main`)
- Optional preview toggles:
  - `PREVIEW_ARTIFACTS_ENABLED=0|1` (default: `1` in dev, `0` in production)
  - `PREVIEW_RESPONSES_ENABLED=0|1` (default: `1` in dev, `0` in production)

When enabled, the server will call `openclaw agent ... --deliver --reply-channel telegram` targeting the originating Telegram chat/user (from verified `initData`).

## Optional: Command Relay Queue (Fly -> ORION host)

If the deployed miniapp server cannot execute `openclaw` locally (common on Fly), enable a relay queue:

- Server env:
  - `COMMAND_RELAY_ENABLED=1`
  - `COMMAND_RELAY_TOKEN=<shared secret>` (or it will fall back to `INGEST_TOKEN`)
- Worker (run on ORION host where `openclaw` is installed):
  - `MINIAPP_COMMAND_RELAY_URL=https://<miniapp-host>`
  - `MINIAPP_COMMAND_RELAY_TOKEN=<same shared secret>`
  - `python3 scripts/miniapp_command_relay.py`

Flow:
1. Miniapp `POST /api/command` enqueues a relay command.
2. ORION host worker claims it via `POST /api/relay/claim`.
3. Worker executes `openclaw agent ... --deliver ...`.
4. Worker reports completion via `POST /api/relay/:id/result`.

## Production Deployment Options

### Option A (simplest): Single Node service (Express serves the built React app)

Deploy to a Node-friendly host like **Fly.io**, **Render**, **Railway**, **AWS ECS**, or **DigitalOcean App Platform**.

- Build command:

```bash
npm ci
npm run build
```

- Start command:

```bash
npm start
```

Environment:
- `PORT`: set by host (Express uses it)
- `HOST`: set to `0.0.0.0` on most hosts

Important: this repo’s `SECURITY.md` prefers loopback by default. The server defaults to `127.0.0.1`; only set `HOST=0.0.0.0` when you intentionally deploy.

## Fly.io (recommended here)

This app includes:
- `apps/telegram-miniapp-dashboard/Dockerfile`
- `apps/telegram-miniapp-dashboard/fly.toml`

Typical flow:

```bash
cd apps/telegram-miniapp-dashboard
fly launch
fly deploy
```

Then set the BotFather Mini App / Web App URL to your Fly HTTPS URL.

### Option B: Static frontend + separate API

- Frontend: Vercel / Netlify / S3+CloudFront
- API: Render/Fly/etc.

If you do this, update the frontend `fetchLiveState` to call the fully-qualified API base URL and configure CORS.

## Registering the Mini App in BotFather

Telegram’s BotFather flow/UI changes over time, but the essentials are stable:

1. Create/select your bot in BotFather.
2. Configure its **Mini App / Web App** settings.
3. Set the **Web App URL** to your deployed HTTPS URL (for example `https://miniapp.example.com`).
4. Set the bot’s allowed **domain** (BotFather typically asks you to set a domain/host for Web Apps).

Requirement: Mini Apps must be served over **HTTPS** on the configured domain.

## Sending a web_app Button from ORION’s Bot (grammY)

ORION’s Telegram plugin uses `grammy` in this repo.

This scaffold includes a suggested `/miniapp` command you can add to ORION’s Telegram plugin that sends a Web App button.

- Set env var `ORION_MINIAPP_URL` (for example `https://miniapp.example.com`).
- Then in Telegram chat with your bot:

```text
/miniapp
```

The bot responds with a button that opens the Mini App.

### OpenClaw CLI Helper (No Bot Code Changes)

If you have OpenClaw configured with your Telegram bot, you can send a `web_app` inline button with:

```bash
ORION_MINIAPP_URL="https://miniapp.example.com" \
  scripts/telegram_send_miniapp_button.sh <chat_id>
```

## Next Hooks (What ORION Will Provide Later)

- Real agent runtime mapping to `POST /api/ingest` (tools/tasks/session lifecycle -> SSE)
- Stronger auth model for SSE consumers (beyond initData privacy + short-lived tokens)
