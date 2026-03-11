import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockAppendEvent = vi.fn();
const mockGetSnapshot = vi.fn();
const mockIsDirectiveOnlyEvent = vi.fn();
const mockQueueDirectiveAction = vi.fn();
const mockValidateEventInput = vi.fn();

vi.mock("@orion-core/db", () => ({
  appendEvent: mockAppendEvent,
  getSnapshot: mockGetSnapshot,
  isDirectiveOnlyEvent: mockIsDirectiveOnlyEvent,
  queueDirectiveAction: mockQueueDirectiveAction,
  validateEventInput: mockValidateEventInput,
}));

describe("POST /api/events", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env = { ...originalEnv, ORION_API_BEARER_TOKEN: "secret" };
    mockValidateEventInput.mockImplementation((body) => body);
    mockAppendEvent.mockReturnValue({ id: "evt-1", type: "MESSAGE_RECEIVED" });
    mockGetSnapshot.mockReturnValue({ events: [] });
    mockIsDirectiveOnlyEvent.mockReturnValue(false);
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("denies unauthorized mutation", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "MESSAGE_RECEIVED", payload: {} }),
      })
    );

    expect(response.status).toBe(401);
    expect(mockAppendEvent).not.toHaveBeenCalled();
  });

  it("accepts authorized mutation", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/events", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          authorization: "Bearer secret",
        },
        body: JSON.stringify({ type: "MESSAGE_RECEIVED", payload: {} }),
      })
    );

    expect(response.status).toBe(200);
    expect(mockAppendEvent).toHaveBeenCalledTimes(1);
  });
});
