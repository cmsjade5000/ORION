import type { Bot } from "grammy";

/**
 * Registers /miniapp to open the Telegram Mini App.
 *
 * This is intentionally simple: it just sends an inline `web_app` button.
 * Later: you can set a Menu Button (BotFather) and/or deep-link users here.
 */
export function registerMiniApp(bot: Bot) {
  bot.command("miniapp", async (ctx) => {
    const raw = String(process.env.ORION_MINIAPP_URL || "").trim();
    let url: string = raw;
    if (!url) {
      await ctx.reply(
        "Mini App URL not configured.\n\nSet ORION_MINIAPP_URL to your deployed HTTPS URL (for example https://<app>.fly.dev) and restart ORION."
      );
      return;
    }

    try {
      const u = new URL(url);
      if (u.protocol !== "https:") {
        await ctx.reply(
          "Mini App URL must be HTTPS.\n\nSet ORION_MINIAPP_URL to your deployed HTTPS URL (for example https://<app>.fly.dev) and restart ORION."
        );
        return;
      }
      // Cache-bust Telegram WebViews: each /miniapp invocation gets a unique URL so old bundles don't stick.
      u.searchParams.set("v", String(Date.now()));
      // Normalize to a string (also prevents accidental whitespace).
      url = u.toString();
    } catch {
      await ctx.reply(
        "Mini App URL is invalid.\n\nSet ORION_MINIAPP_URL to your deployed HTTPS URL (for example https://<app>.fly.dev) and restart ORION."
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
