import type { EventInput } from "@orion-core/db";

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
  try {
    const { appendEvent, getSnapshot, isDirectiveEventType, queueDirectiveAction } = await import("@orion-core/db");
    const body = (await request.json()) as EventInput & {
      operator?: { telegramUserId?: number | string | null };
    };
    if (!body?.type) {
      return Response.json({ error: "Missing event type" }, { status: 400 });
    }

    const event = appendEvent({ type: body.type, payload: body.payload ?? {} });
    if (isDirectiveEventType(event.type)) {
      queueDirectiveAction(event as Parameters<typeof queueDirectiveAction>[0], asDeliverTarget(body.operator?.telegramUserId));
    }

    return Response.json(getSnapshot());
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Failed to append event"
      },
      { status: 500 }
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
