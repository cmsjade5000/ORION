import type { EventInput } from "@orion-core/db";
import { authorizeMutationRequest, mutationAuthErrorResponse } from "../../../lib/mutation-auth";

export const runtime = "nodejs";

function asDeliverTarget(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return String(Math.trunc(value));
  }
  if (typeof value === "string" && /^[0-9]+$/.test(value.trim())) {
    return value.trim();
  }
  return null;
}

export async function POST(request: Request): Promise<Response> {
  const auth = authorizeMutationRequest(request);
  if (!auth.ok) {
    return mutationAuthErrorResponse(auth);
  }

  try {
    const { appendEvent, getSnapshot, isDirectiveOnlyEvent, queueDirectiveAction, validateEventInput } = await import("@orion-core/db");
    const body = (await request.json()) as EventInput & {
      operator?: { telegramUserId?: number | string | null };
    };
    const eventInput = validateEventInput(body);

    const event = appendEvent(eventInput);
    if (isDirectiveOnlyEvent(eventInput)) {
      queueDirectiveAction(event as Parameters<typeof queueDirectiveAction>[0], asDeliverTarget(body.operator?.telegramUserId));
    }

    return Response.json(getSnapshot());
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to append event";
    const status = /Invalid|Missing|Unsupported/.test(message) ? 400 : 500;
    return Response.json(
      {
        error: message
      },
      { status }
    );
  }
}

export async function GET(): Promise<Response> {
  try {
    const { getSnapshot } = await import("@orion-core/db");
    return Response.json(getSnapshot().events);
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Failed to load events"
      },
      { status: 500 }
    );
  }
}
