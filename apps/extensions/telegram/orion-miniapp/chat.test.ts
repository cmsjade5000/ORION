import { describe, expect, it } from "vitest";

const { createChatManager, defaultExecuteTurn, stableConversationId, stableSessionId, userFacingRuntimeError } = require("./chat.cjs");

describe("mini app chat manager", () => {
  it("creates stable bridge ids", () => {
    expect(stableConversationId("123")).toBe("miniapp-123-main");
    expect(stableSessionId("123")).toBe("miniapp-session-123");
  });

  it("queues a run and appends the assistant reply", async () => {
    const manager = createChatManager({
      workspaceRoot: process.cwd(),
      executeTurn: async () => ({ ok: true, text: "Bridge answer.", error: "" }),
    });

    const initial = manager.bootstrap({ id: 12345 });
    expect(initial.messages).toHaveLength(0);

    const queued = manager.createRun({ id: 12345 }, "Ping the bridge");
    expect(queued.status).toBe("queued");
    expect(queued.conversation.messages.at(-1)).toMatchObject({
      role: "user",
      text: "Ping the bridge",
    });

    await new Promise((resolve) => setTimeout(resolve, 25));
    const completed = manager.getRun(queued.runId);
    expect(completed.status).toBe("completed");
    expect(completed.conversation.messages.at(-1)).toMatchObject({
      role: "assistant",
      text: "Bridge answer.",
    });
  });

  it("normalizes runtime errors into bridge-friendly copy", () => {
    expect(userFacingRuntimeError("timed out after 180s")).toContain("too long");
    expect(userFacingRuntimeError("something awful happened")).toContain("runtime snag");
  });

  it("keeps default bridge turns on a bounded timeout", () => {
    const source = defaultExecuteTurn.toString();
    expect(source).toContain("ORION_MINIAPP_TURN_TIMEOUT_SECONDS");
    expect(source).toContain('"90"');
    expect(source).toContain("child.kill");
  });
});
