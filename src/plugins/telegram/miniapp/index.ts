import type { Bot } from "grammy";

/**
 * Registers /miniapp to open the Telegram Mini App.
 *
 * This is intentionally simple: it just sends an inline `web_app` button.
 * Later: you can set a Menu Button (BotFather) and/or deep-link users here.
 */
export function registerMiniApp(bot: Bot) {
  bot.command("miniapp", async (ctx) => {
    const url = process.env.ORION_MINIAPP_URL;
    if (!url) {
      await ctx.reply(
        "Mini App URL not configured.\n\nSet ORION_MINIAPP_URL to your deployed HTTPS URL (for example https://<app>.fly.dev) and restart ORION."
      );
      return;
    }

    await ctx.reply("Open ORION Network Dashboard:", {
      reply_markup: {
        inline_keyboard: [
          [
            {
              text: "Open Dashboard",
              web_app: { url },
            },
          ],
        ],
      },
    });
  });
}
