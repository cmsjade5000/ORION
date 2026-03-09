export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  try {
    const payload = (await request.json()) as Record<string, unknown>;
    return Response.json({ ok: true, accepted: true, type: payload?.type ?? null });
  } catch {
    return Response.json({ ok: true, accepted: true, type: null });
  }
}
