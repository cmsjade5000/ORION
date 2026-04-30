import { describe, expect, it } from "vitest";

import { ChatTaskQueue } from "./queue";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe("ChatTaskQueue", () => {
  it("serializes tasks for the same chat id", async () => {
    const queue = new ChatTaskQueue();
    const events: string[] = [];

    const first = queue.enqueue(42, async () => {
      events.push("first:start");
      await sleep(10);
      events.push("first:end");
      return "first";
    });
    const second = queue.enqueue(42, async () => {
      events.push("second:start");
      events.push("second:end");
      return "second";
    });

    await expect(Promise.all([first, second])).resolves.toEqual(["first", "second"]);
    expect(events).toEqual(["first:start", "first:end", "second:start", "second:end"]);
  });

  it("allows different chats to run concurrently", async () => {
    const queue = new ChatTaskQueue();
    const events: string[] = [];

    const first = queue.enqueue(1, async () => {
      events.push("one:start");
      await sleep(20);
      events.push("one:end");
    });
    const second = queue.enqueue(2, async () => {
      events.push("two:start");
      events.push("two:end");
    });

    await Promise.all([first, second]);
    expect(events.indexOf("two:start")).toBeGreaterThan(-1);
    expect(events.indexOf("two:start")).toBeLessThan(events.indexOf("one:end"));
  });

  it("continues after the previous task rejects", async () => {
    const queue = new ChatTaskQueue();
    const events: string[] = [];

    const first = queue.enqueue(7, async () => {
      events.push("first:start");
      throw new Error("boom");
    });
    const second = queue.enqueue(7, async () => {
      events.push("second:start");
      return "recovered";
    });

    await expect(first).rejects.toThrow("boom");
    await expect(second).resolves.toBe("recovered");
    expect(events).toEqual(["first:start", "second:start"]);
  });
});
