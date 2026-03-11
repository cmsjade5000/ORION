export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  return Response.json(
    {
      ok: true,
      service: "orion-core-app",
      check: "readyz",
      timestamp: new Date().toISOString()
    },
    { status: 200 }
  );
}
