// Proxies a scanned photo, PDF or document to the backend's reader (SPEC §14), so the backend
// URL stays on the server. The backend only transcribes; the student reviews the text before
// anything is checked.

import { BACKEND_URL } from "@/lib/api";

const MAX_BYTES = 15 * 1024 * 1024;

function problem(status: number, detail: string): Response {
  return Response.json({ detail }, { status });
}

export async function POST(request: Request): Promise<Response> {
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > MAX_BYTES) return problem(413, "That file is too big (the limit is 15 MB).");
  const body = await request.arrayBuffer();
  if (body.byteLength === 0) return problem(400, "The file is empty.");
  if (body.byteLength > MAX_BYTES)
    return problem(413, "That file is too big (the limit is 15 MB).");

  const headers: Record<string, string> = {
    "content-type": request.headers.get("content-type") ?? "application/octet-stream",
    accept: "application/json",
  };
  const filename = request.headers.get("x-filename");
  if (filename) headers["x-filename"] = filename.slice(0, 200);

  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}/read`, { method: "POST", body, headers });
  } catch {
    return problem(503, "ProofLab's reader isn't running. Start the backend and try again.");
  }
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    return problem(502, "The reader sent back something ProofLab couldn't use.");
  }
  return Response.json(data, { status: res.status });
}
