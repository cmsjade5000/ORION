import { Bot, InlineKeyboard } from "grammy";
import { requireOperatorAccess } from "./access";

const DEFAULT_MINIAPP_URL = "https://mac-mini.tail5e899c.ts.net";

export function normalizeMiniAppUrl(raw?: string): string {
  const value = String(raw || DEFAULT_MINIAPP_URL).trim();
  return value.replace(/\/+$/, "");
}

export function buildMiniAppUrl(startapp = "home"): string {
  const url = new URL(normalizeMiniAppUrl(process.env.ORION_MINIAPP_URL));
  if (startapp) {
    url.searchParams.set("startapp", startapp);
  }
  return url.toString();
}

export function orionLaunchKeyboard(startapp = "home"): InlineKeyboard {
  const url = buildMiniAppUrl(startapp);
  return new InlineKeyboard().webApp("Open ORION", url).row().url("Open Link", url);
}

export async function maybeConfigureMenuButton(bot: Bot): Promise<void> {
  const shouldConfigure = String(process.env.ORION_MINIAPP_SET_MENU_BUTTON || "1").trim() !== "0";
  if (!shouldConfigure) return;

  try {
    await bot.api.setChatMenuButton({
      menu_button: {
        type: "web_app",
        text: "ORION",
        web_app: { url: buildMiniAppUrl("home") },
      },
    });
  } catch {
    // Ignore startup configuration failures; BotFather/manual setup remains valid.
  }
}

export function registerMiniAppLaunch(bot: Bot): void {
  bot.command("orion", async (ctx) => {
    if (!(await requireOperatorAccess(ctx, "ORION Mini App"))) return;
    await ctx.reply("Open the ORION control surface:", {
      reply_markup: orionLaunchKeyboard("home"),
    });
  });
}
