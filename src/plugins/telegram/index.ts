import { Bot } from "grammy";
import { registerAssistantCommands } from "./assistant";
import { registerDashboard } from "./dashboard";
import { maybeConfigureMenuButton, registerMiniAppLaunch } from "./miniapp";

/**
 * Sets up the ORION core Telegram surface.
 *
 * Non-core product surfaces such as trading, game, and media workflows stay in
 * the repo for now, but they are not registered on the default core bot path.
 */
export function setupTelegramPlugin(bot: Bot) {
  registerAssistantCommands(bot);
  registerMiniAppLaunch(bot);
  registerDashboard(bot);
  void maybeConfigureMenuButton(bot);
}
