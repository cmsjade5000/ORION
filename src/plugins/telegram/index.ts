import { Bot } from "grammy";
import { registerDashboard } from "./dashboard";
import { registerFlicChatRouter } from "./flic";
import { registerKalshiCommands } from "./kalshi";
import { registerMiniApp } from "./miniapp";

/**
 * Sets up Telegram plugin features (Agent Dashboard).
 */
export function setupTelegramPlugin(bot: Bot) {
  registerDashboard(bot);
  registerMiniApp(bot);
  registerKalshiCommands(bot);
  registerFlicChatRouter(bot);
}
