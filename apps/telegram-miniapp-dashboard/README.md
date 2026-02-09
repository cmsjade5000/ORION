# ORION Telegram Mini App: Network Dashboard (Starter)

This is a starter scaffold for a **Telegram Mini App** that opens from ORION’s bot and renders a live network dashboard.

## What’s Included

- React + Vite app, mobile-first layout
- Telegram WebApp SDK integration (reads `Telegram.WebApp.initData` when available)
- Network UI
  - Central `ORION` node
  - Orbiting sub-agent nodes: `ATLAS`, `EMBER`, `PIXEL`, `AEGIS`, `LEDGER`
  - Animated connection line `ORION -> active agent` (placeholder)
  - Placeholder node pulse animation
  - Command bar UI (placeholder)
- Express backend
  - `GET /api/state` mock live state
  - `POST /api/sse-auth` + `GET /api/events` SSE stream (push updates)
  - `POST /api/ingest` ORION -> Mini App event ingest (rebroadcasts over SSE)
  - `POST /api/command` stub command ingestion (`202 accepted`)
  - Serves `dist/` in production

## SSE Event Types (v0)

The SSE endpoint (`GET /api/events`) emits:

- `state`: periodic full snapshot (recovery + UI render source of truth)
- `agent.activity`
- `tool.started`, `tool.finished`, `tool.failed`
- `task.created`, `task.routed`, `task.started`, `task.completed`, `task.failed`

Notes:
- The server will also emit some extra convenience events (for example `command.accepted`) during development.
- `state` frames are the authoritative UI state; the fine-grained events exist for low-latency UX and future replay/debugging.

## ORION -> Mini App Ingest (v0)

ORION (or a bridge) POSTs events to `POST /api/ingest`.

Auth:
- `Authorization: Bearer $INGEST_TOKEN`

Environment:
- `INGEST_TOKEN`: shared secret for service-to-service auth (set as a Fly secret)
- `MOCK_STATE`: default `1`. When `0`, the server stops generating mock motion and relies on ORION events.

Example payloads:

```json
{ "type": "agent.activity", "agentId": "ATLAS", "activity": "search", "ts": 1739068800000 }
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

## Next Hooks (What ORION Will Provide Later)

- Backend signature verification for `initData` (bind requests to Telegram user)
- Real agent runtime mapping to `GET /api/events` (push) and/or `GET /api/state` (fallback)
- Command endpoint (POST) that routes to ORION task packets / sessions
