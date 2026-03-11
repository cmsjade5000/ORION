import { describe, expect, it } from "vitest";
import { validateEventInput, validateRelayClaimRequest, validateRelayResultRequest } from "./contracts";

describe("db contracts", () => {
  it("validates directive events with typed payloads", () => {
    expect(
      validateEventInput({
        type: "INJECT_TASK_PACKET",
        payload: { type: "research", objective: "Map provider lanes" }
      })
    ).toEqual({
      type: "INJECT_TASK_PACKET",
      payload: { type: "research", objective: "Map provider lanes" }
    });
  });

  it("rejects invalid event payloads", () => {
    expect(() =>
      validateEventInput({
        type: "INJECT_TASK_PACKET",
        payload: { type: "bad-type" }
      })
    ).toThrow(/Invalid INJECT_TASK_PACKET type/);
  });

  it("normalizes relay claim requests", () => {
    expect(validateRelayClaimRequest({})).toEqual({ workerId: "relay-worker" });
    expect(validateRelayClaimRequest({ workerId: " worker-1 " })).toEqual({ workerId: "worker-1" });
  });

  it("requires worker and claim token on relay results", () => {
    expect(
      validateRelayResultRequest({
        ok: true,
        code: 200,
        responseText: "done",
        error: "",
        workerId: "worker-1",
        claimToken: "token-1"
      })
    ).toEqual({
      ok: true,
      code: 200,
      responseText: "done",
      error: null,
      workerId: "worker-1",
      claimToken: "token-1"
    });

    expect(() =>
      validateRelayResultRequest({
        ok: true,
        workerId: "worker-1"
      })
    ).toThrow(/Missing relay worker or claim token/);
  });
});
