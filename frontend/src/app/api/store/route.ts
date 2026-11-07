// Proxies the browser's sync requests to the progress database on the backend (SPEC §17), so
// the backend URL stays on the server.

import { BACKEND_URL } from "@/lib/api";

const MAX_BYTES = 4 * 1024 * 1024;

function problem(status: number, detail: string): Response {
  return Response.json({ detail }, { status });
}

async function forward(init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/store`, { ...init, cache: "no-store" });
  } catch {
    return problem(503, "ProofLab's database isn't reachable. Changes stay in this browser.");
  }
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(): Promise<Response> {
  return forward({ headers: { accept: "application/json" } });
}

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  if (body.length > MAX_BYTES) return problem(413, "Too many changes at once.");
  return forward({
    method: "POST",
    body,
    headers: { "content-type": "application/json", accept: "application/json" },
  });
}
