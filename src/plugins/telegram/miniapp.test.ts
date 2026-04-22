import { describe, expect, it, vi } from "vitest";
import type { Bot } from "grammy";
import { buildMiniAppUrl, maybeConfigureMenuButton, normalizeMiniAppUrl, orionLaunchKeyboard, registerMiniAppLaunch } from "./miniapp";

describe("Telegram mini app launch helpers", () => {
  it("normalizes the mini app base url", () => {
    expect(normalizeMiniAppUrl("https://example.com///")).toBe("https://example.com");
  });

  it("builds startapp deep links", () => {
    process.env.ORION_MINIAPP_URL = "https://example.com/app";
    expect(buildMiniAppUrl("capture")).toBe("https://example.com/app?startapp=capture");
  });

  it("creates a launch keyboard with a web app button", () => {
    process.env.ORION_MINIAPP_URL = "https://example.com/app";
    const keyboard = orionLaunchKeyboard("review");
    expect(keyboard.inline_keyboard[0]?.[0]).toMatchObject({
      text: "Open ORION",
      web_app: { url: "https://example.com/app?startapp=review" },
    });
  });

  it("registers /orion", () => {
    const bot = { command: vi.fn() } as any as Bot;
    registerMiniAppLaunch(bot);
    expect(bot.command).toHaveBeenCalledWith("orion", expect.any(Function));
  });

  it("attempts to configure the menu button", async () => {
    process.env.ORION_MINIAPP_URL = "https://example.com/app";
    const setChatMenuButton = vi.fn().mockResolvedValue(true);
    const bot = { api: { setChatMenuButton } } as any as Bot;
    await maybeConfigureMenuButton(bot);
    expect(setChatMenuButton).toHaveBeenCalledWith({
      menu_button: {
        type: "web_app",
        text: "ORION",
        web_app: { url: "https://example.com/app?startapp=home" },
      },
    });
  });
});
