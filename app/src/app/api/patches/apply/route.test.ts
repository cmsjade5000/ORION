import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockAppendEvent = vi.fn();
const mockGetSnapshot = vi.fn();
const mockIsPatchId = vi.fn();

vi.mock("@orion-core/db", () => ({
  appendEvent: mockAppendEvent,
  getSnapshot: mockGetSnapshot,
}));

vi.mock("@orion-core/db/patches", () => ({
  isPatchId: mockIsPatchId,
}));

describe("POST /api/patches/apply", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env = { ...originalEnv, ORION_API_BEARER_TOKEN: "secret" };
    mockIsPatchId.mockReturnValue(true);
    mockGetSnapshot.mockReturnValue({ events: [] });
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("denies unauthorized patch application", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/patches/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patchId: "patch-1" }),
      })
    );

    expect(response.status).toBe(401);
    expect(mockAppendEvent).not.toHaveBeenCalled();
  });

  it("accepts authorized patch application", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/patches/apply", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          authorization: "Bearer secret",
        },
        body: JSON.stringify({ patchId: "patch-1" }),
      })
    );

    expect(response.status).toBe(200);
    expect(mockAppendEvent).toHaveBeenCalledWith({
      type: "PATCH_APPLIED",
      payload: { patchId: "patch-1" },
    });
  });
});
