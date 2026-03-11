import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("POST /api/ingest", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv, ORION_API_BEARER_TOKEN: "secret" };
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it("denies unauthorized ingest", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "PING" }),
      })
    );

    expect(response.status).toBe(401);
  });

  it("accepts authorized ingest", async () => {
    const { POST } = await import("./route");
    const response = await POST(
      new Request("https://example.test/api/ingest", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          authorization: "Bearer secret",
        },
        body: JSON.stringify({ type: "PING" }),
      })
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual({ ok: true, accepted: true, type: "PING" });
  });
});
