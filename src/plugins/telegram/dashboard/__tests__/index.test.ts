import { Bot } from "grammy";
import { registerDashboard } from "../index";

describe("Agent Dashboard command registration", () => {
  it("should register the /agents command", () => {
    const bot = { command: jest.fn() } as any as Bot;
    registerDashboard(bot);
    expect(bot.command).toHaveBeenCalledWith(
      "agents",
      expect.any(Function)
    );
  });
});
