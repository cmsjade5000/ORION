import { beforeEach, describe, expect, it, vi } from "vitest";

const mockClaimDirectiveAction = vi.fn();
const mockValidateRelayClaimRequest = vi.fn();
const mockRelayEnabled = vi.fn();
const mockRelayAuthOk = vi.fn();
const mockRelayAgentId = vi.fn();

vi.mock("@orion-core/db", () => ({
  claimDirectiveAction: mockClaimDirectiveAction,
  validateRelayClaimRequest: mockValidateRelayClaimRequest,
}));

vi.mock("@/lib/relay", () => ({
  relayEnabled: mockRelayEnabled,
  relayAuthOk: mockRelayAuthOk,
  relayAgentId: mockRelayAgentId,
}));

describe("POST /api/relay/claim", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockRelayEnabled.mockReturnValue(true);
    mockRelayAuthOk.mockReturnValue(true);
    mockRelayAgentId.mockReturnValue("main");
    mockValidateRelayClaimRequest.mockReturnValue({ workerId: "worker-1" });
  });

  it("returns lease metadata for a claimed command", async () => {
    mockClaimDirectiveAction.mockReturnValue({
      id: "12",
      commandText: "Run diagnostics",
      deliverTarget: "123",
      createdAt: "2026-03-11T00:00:00.000Z",
      leaseUntil: "2026-03-11T00:01:00.000Z",
      claimToken: "claim-123",
    });

    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/relay/claim", {
        method: "POST",
        body: JSON.stringify({ workerId: "worker-1" }),
      })
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.command.claimToken).toBe("claim-123");
    expect(body.command.leaseUntil).toBe(Date.parse("2026-03-11T00:01:00.000Z"));
  });

  it("rejects invalid relay bodies", async () => {
    mockValidateRelayClaimRequest.mockImplementation(() => {
      throw new Error("bad body");
    });
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/relay/claim", {
        method: "POST",
        body: JSON.stringify({}),
      })
    );

    expect(response.status).toBe(400);
  });
});
