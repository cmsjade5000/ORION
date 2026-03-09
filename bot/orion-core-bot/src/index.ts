import { Markup, Telegraf } from "telegraf";

function getRequiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

const botToken = getRequiredEnv("BOT_TOKEN");
const webAppUrl = getRequiredEnv("WEBAPP_URL");

// Fail fast if WEBAPP_URL is not a valid absolute URL.
new URL(webAppUrl);

const bot = new Telegraf(botToken);

const introText =
  "Welcome to ORION Core. Tap the button below to open the Mini App.";

const webAppKeyboard = Markup.inlineKeyboard([
  Markup.button.webApp("Open ORION Core", webAppUrl)
]);

async function sendCoreEntry(ctx: { reply: (text: string, extra?: object) => Promise<unknown> }): Promise<void> {
  await ctx.reply(introText, webAppKeyboard);
}

bot.start(async (ctx) => {
  await sendCoreEntry(ctx);
});

bot.command("core", async (ctx) => {
  await sendCoreEntry(ctx);
});

bot.catch((err) => {
  console.error("Unhandled bot error:", err);
});

async function main(): Promise<void> {
  await bot.launch();
  console.log("ORION Core bot is running");
}

void main();

process.once("SIGINT", () => {
  bot.stop("SIGINT");
});

process.once("SIGTERM", () => {
  bot.stop("SIGTERM");
});
