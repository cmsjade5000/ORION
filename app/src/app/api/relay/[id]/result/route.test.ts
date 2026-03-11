import { beforeEach, describe, expect, it, vi } from "vitest";

const mockCompleteDirectiveAction = vi.fn();
const mockValidateRelayResultRequest = vi.fn();
const mockRelayEnabled = vi.fn();
const mockRelayAuthOk = vi.fn();

vi.mock("@orion-core/db", () => ({
  completeDirectiveAction: mockCompleteDirectiveAction,
  validateRelayResultRequest: mockValidateRelayResultRequest,
}));

vi.mock("@/lib/relay", () => ({
  relayEnabled: mockRelayEnabled,
  relayAuthOk: mockRelayAuthOk,
}));

describe("POST /api/relay/[id]/result", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockRelayEnabled.mockReturnValue(true);
    mockRelayAuthOk.mockReturnValue(true);
    mockValidateRelayResultRequest.mockReturnValue({
      ok: true,
      code: 200,
      responseText: "done",
      error: null,
      workerId: "worker-1",
      claimToken: "claim-1",
    });
  });

  it("completes a command with a valid lease", async () => {
    mockCompleteDirectiveAction.mockReturnValue({ id: "12", status: "completed" });
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/relay/12/result", {
        method: "POST",
        body: JSON.stringify({ ok: true, workerId: "worker-1", claimToken: "claim-1" }),
      }),
      { params: Promise.resolve({ id: "12" }) }
    );

    expect(response.status).toBe(200);
    expect(mockCompleteDirectiveAction).toHaveBeenCalledWith("12", "worker-1", "claim-1", {
      ok: true,
      code: 200,
      responseText: "done",
      error: null,
    });
  });

  it("returns 400 for invalid payloads", async () => {
    mockValidateRelayResultRequest.mockImplementation(() => {
      throw new Error("invalid");
    });
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/relay/12/result", {
        method: "POST",
        body: JSON.stringify({}),
      }),
      { params: Promise.resolve({ id: "12" }) }
    );

    expect(response.status).toBe(400);
  });
});
