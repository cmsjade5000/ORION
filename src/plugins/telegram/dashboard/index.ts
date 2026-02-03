import { Bot, InlineKeyboard } from "grammy";

/**
 * Registers the /agents command to display the Agent Dashboard inline keyboard.
 */
export function registerDashboard(bot: Bot) {
  bot.command("agents", async (ctx) => {
    const keyboard = new InlineKeyboard()
      .text("ORION", "agent_ORION")
      .text("EMBER", "agent_EMBER")
      .row()
      .text("ATLAS", "agent_ATLAS")
      .text("PIXEL", "agent_PIXEL")
      .row()
      .text("NODE", "agent_NODE")
      .text("LEDGER", "agent_LEDGER");

    await ctx.reply("Select an agent to view details:", {
      reply_markup: keyboard,
    });
  });
}
