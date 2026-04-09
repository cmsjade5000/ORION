import { Bot } from "grammy";
import { registerAssistantCommands } from "./assistant";
import { registerDashboard } from "./dashboard";
import { registerFlicChatRouter } from "./flic";
import { registerKalshiCommands } from "./kalshi";
import { registerPogoCommands } from "./pogo";

/**
 * Sets up Telegram plugin features (Agent Dashboard).
 */
export function setupTelegramPlugin(bot: Bot) {
  registerAssistantCommands(bot);
  registerDashboard(bot);
  registerKalshiCommands(bot);
  registerPogoCommands(bot);
  registerFlicChatRouter(bot);
}
