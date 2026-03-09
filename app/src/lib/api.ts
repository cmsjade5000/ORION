import type {
  EventInput,
  OrionEventPayloadMap,
  OrionEventType,
  OrionSnapshot,
  PatchId
} from "@orion-core/db";

async function assertOk(response: Response): Promise<Response> {
  if (response.ok) {
    return response;
  }

  let message = "Request failed";
  try {
    const data = (await response.json()) as { error?: string };
    if (data.error) {
      message = data.error;
    }
  } catch {
    message = `Request failed (${response.status})`;
  }

  throw new Error(message);
}

export async function fetchSnapshot(): Promise<OrionSnapshot> {
  const response = await fetch("/api/state", { method: "GET", cache: "no-store" });
  await assertOk(response);
  return (await response.json()) as OrionSnapshot;
}

export async function dispatchEvent<T extends OrionEventType>(
  type: T,
  payload: OrionEventPayloadMap[T] = {} as OrionEventPayloadMap[T],
  operator?: { telegramUserId?: number | string | null }
): Promise<OrionSnapshot> {
  const event: EventInput<T> = { type, payload };
  const response = await fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...event, operator })
  });

  await assertOk(response);
  return (await response.json()) as OrionSnapshot;
}

export async function applyPatch(patchId: PatchId): Promise<OrionSnapshot> {
  const response = await fetch("/api/patches/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patchId })
  });

  await assertOk(response);
  return (await response.json()) as OrionSnapshot;
}
