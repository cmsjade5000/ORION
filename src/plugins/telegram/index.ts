import { Bot } from "grammy";
import { registerDashboard } from "./dashboard";
import { registerMiniApp } from "./miniapp";

/**
 * Sets up Telegram plugin features (Agent Dashboard).
 */
export function setupTelegramPlugin(bot: Bot) {
  registerDashboard(bot);
  registerMiniApp(bot);
}
