import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("relay auth", () => {
  const env = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    process.env.MINIAPP_COMMAND_RELAY_TOKEN = "relay-secret";
  });

  afterEach(() => {
    process.env = { ...env };
  });

  it("builds and validates signed relay headers", async () => {
    const { buildRelayAuthHeaders, relayAuthOk } = await import("./relay");
    const body = JSON.stringify({ workerId: "worker-1" });
    const headers = buildRelayAuthHeaders("POST", "/api/relay/claim", body);
    const request = new Request("https://example.test/api/relay/claim", {
      method: "POST",
      headers,
      body
    });

    expect(relayAuthOk(request, body, "/api/relay/claim")).toBe(true);
  });

  it("rejects replayed nonces", async () => {
    const { buildRelayAuthHeaders, relayAuthOk } = await import("./relay");
    const body = JSON.stringify({ workerId: "worker-1" });
    const headers = buildRelayAuthHeaders("POST", "/api/relay/claim", body);

    const first = new Request("https://example.test/api/relay/claim", {
      method: "POST",
      headers,
      body
    });
    const second = new Request("https://example.test/api/relay/claim", {
      method: "POST",
      headers,
      body
    });

    expect(relayAuthOk(first, body, "/api/relay/claim")).toBe(true);
    expect(relayAuthOk(second, body, "/api/relay/claim")).toBe(false);
  });
});
