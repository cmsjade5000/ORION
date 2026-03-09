# ORION Core Bot

Minimal Telegram bot scaffold for ORION Core Mini App.

## Environment variables

- `BOT_TOKEN` (required): Telegram bot token from BotFather.
- `WEBAPP_URL` (required): Absolute HTTPS URL for the ORION Core Mini App.

## Run

```bash
npm install
npm run build
npm start
```

## Behavior

- `/start`: Sends intro text with a Telegram WebApp button pointing to `WEBAPP_URL`.
- `/core`: Sends the same response as `/start`.
