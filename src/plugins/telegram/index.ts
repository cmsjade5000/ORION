import { Bot } from "grammy";
import { registerDashboard } from "./dashboard";

/**
 * Sets up Telegram plugin features (Agent Dashboard).
 */
export function setupTelegramPlugin(bot: Bot) {
  registerDashboard(bot);
}
