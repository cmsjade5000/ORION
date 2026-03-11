import { claimDirectiveAction, validateRelayClaimRequest } from "@orion-core/db";
import { relayAgentId, relayAuthOk, relayEnabled } from "@/lib/relay";

export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  if (!relayEnabled()) {
    return Response.json(
      { ok: false, error: { code: "DISABLED", message: "Command relay is disabled" } },
      { status: 503 }
    );
  }

  const rawBody = await request.text();
  if (!relayAuthOk(request, rawBody, "/api/relay/claim")) {
    return Response.json(
      { ok: false, error: { code: "UNAUTHORIZED", message: "Bad relay token" } },
      { status: 401 }
    );
  }

  try {
    const parsedBody = rawBody ? JSON.parse(rawBody) : {};
    const { workerId } = validateRelayClaimRequest(parsedBody);
    const run = claimDirectiveAction(workerId);
    if (!run || !run.commandText || !run.deliverTarget) {
      return Response.json({ ok: true, command: null });
    }

    return Response.json({
      ok: true,
      command: {
        id: run.id,
        text: run.commandText,
        deliverTarget: run.deliverTarget,
        agentId: relayAgentId(),
        acceptedAt: new Date(run.createdAt).getTime(),
        leaseUntil: run.leaseUntil ? Date.parse(run.leaseUntil) : null,
        claimToken: run.claimToken
      }
    });
  } catch (error) {
    return Response.json(
      { ok: false, error: { code: "BAD_REQUEST", message: error instanceof Error ? error.message : "Invalid relay body" } },
      { status: 400 }
    );
  }
}
