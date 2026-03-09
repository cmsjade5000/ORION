# ORION Core (Telegram Mini App)

ORION Core is a new, standalone Telegram Mini App + bot pair designed for mobile-first monitoring of a local AI core state.

## Project Layout

- `/Users/corystoner/src/ORION/app` → Next.js (TypeScript) Mini App UI + API routes
- `/Users/corystoner/src/ORION/db` → SQLite + event log + reducer core
- `/Users/corystoner/src/ORION/bot/orion-core-bot` → Telegram bot that opens the Mini App

## Local Development

### 1) Install app dependencies

```bash
cd /Users/corystoner/src/ORION/app
npm install
```

### 2) Run the Mini App locally

```bash
npm run dev
```

Default URL: `http://localhost:3000`

### 3) Optional environment variables

- `ORION_CORE_DB_PATH` (optional): absolute path to SQLite file
  - default: `../db/orion-core.sqlite` relative to `/app`
- `ORION_CORE_TIMEZONE` (optional): timezone for daily sync/missed checks
  - default: `America/New_York`

Example:

```bash
ORION_CORE_DB_PATH=/Users/corystoner/src/ORION/db/orion-core.sqlite ORION_CORE_TIMEZONE=America/New_York npm run dev
```

## Telegram Bot + Mini App Setup

### 1) Create a bot with BotFather

1. Open Telegram and chat with [@BotFather](https://t.me/BotFather)
2. Run `/newbot`
3. Save the generated bot token

### 2) Configure Mini App URL in BotFather

Use BotFather Mini App/Web App setup for your bot and set the URL to your deployed app URL.

For local testing with Telegram, expose localhost via HTTPS tunnel (Cloudflare Tunnel or ngrok), then use that HTTPS URL as your WebApp URL.

### 3) Configure and run ORION Core bot

```bash
cd /Users/corystoner/src/ORION/bot/orion-core-bot
npm install
BOT_TOKEN=your_bot_token WEBAPP_URL=https://your-miniapp-url npm run dev
```

Bot commands:
- `/start` → sends a button that opens ORION Core Mini App
- `/core` → same action

## Setting `WEBAPP_URL`

`WEBAPP_URL` must be the HTTPS URL where `/app` is reachable.

- Local tunnel example:
  - `WEBAPP_URL=https://abc123.ngrok-free.app`
- Vercel example:
  - `WEBAPP_URL=https://orion-core.vercel.app`

## Deployment Notes

### App (Vercel or Node host)

- Deploy `/Users/corystoner/src/ORION/app` as a Next.js app.
- Ensure runtime supports native Node modules (`better-sqlite3`).
- For persistent SQLite in production, attach persistent storage (or move to managed DB later).

### Actionable Directives (v1.1)

Directives now produce both:
- Event log state updates (XP, streaks, mood, etc.)
- Optional relay-backed real actions routed into ORION/OpenClaw

Current bindings:
- `Daily Sync` -> cohesion sync across core specialists + drift report
- `Run Diagnostics` -> workspace diagnostics sweep + prioritized fixes
- `Flush Cache` -> safe context hygiene pass (reversible only)
- `Inject Task Packet` -> create and run a specialist task packet

Use the `Objective Focus` field in the Directives tab to attach a concrete goal to each run.

### Enabling Relay-Backed Real Actions

If app hosting cannot execute `openclaw` directly (for example Fly/Vercel), use the command relay worker on your Mac:

1. Set relay token on the app host:
   - `MINIAPP_INGEST_TOKEN=<shared-secret>` (or `MINIAPP_COMMAND_RELAY_TOKEN`)
2. Ensure Mini App URL is configured in OpenClaw (`ORION_MINIAPP_URL`).
3. Install/start LaunchAgent worker on your Mac:

```bash
cd /Users/corystoner/src/ORION
./scripts/install_orion_miniapp_command_relay_launchagent.sh /Users/corystoner/src/ORION
```

4. Optional fallback delivery target (if Telegram WebApp user id is unavailable):
   - `ORION_CORE_TELEGRAM_TARGET=<your_telegram_user_id>`
   - or `ORION_TELEGRAM_CHAT_ID=<your_telegram_user_id>`

With relay enabled, action status appears in `Directives -> Live Actions` as `Queued/In Progress/Completed/Failed`.

### Bot (any Node host)

- Deploy `/Users/corystoner/src/ORION/bot/orion-core-bot`
- Set env vars:
  - `BOT_TOKEN`
  - `WEBAPP_URL`

## Raspberry Pi Kiosk Mode (Future)

ORION Core is designed to run unchanged on a ~3.5" display.

Recommended setup:

1. Launch Chromium in kiosk mode to app URL (local or remote)
2. Enable Pi Mode inside app Settings:
   - Larger fonts
   - Increased spacing
   - Reduced animation
3. Keep viewport around mobile width for consistent layout

Example kiosk launch:

```bash
chromium-browser --kiosk http://localhost:3000 --noerrdialogs --disable-infobars
```
