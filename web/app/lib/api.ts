// Thin client for the FastAPI backend.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Source = {
  id: number;
  name: string;
  status: "processing" | "ready" | "error";
  duration_ms: number | null;
  error?: string | null;
  segment_count?: number;
};

export type SegHit = {
  id: number;
  seq: number;
  text: string;
  start_ms: number;
  end_ms: number;
  score: number;
  audio_url: string | null;
};

export type SearchResponse = {
  query: string;
  source_id: number | null;
  count: number;
  results: SegHit[];
};

async function jsonOrThrow(res: Response) {
  if (!res.ok) {
    let msg = `request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) msg = body.detail;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export async function uploadSource(
  file: File,
  name: string,
): Promise<{ source_id: number; status: string; duration_ms: number }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("name", name);
  return jsonOrThrow(await fetch(`${API}/api/sources`, { method: "POST", body: fd }));
}

export async function getSource(id: number): Promise<Source> {
  return jsonOrThrow(await fetch(`${API}/api/sources/${id}`));
}

export async function listSources(): Promise<Source[]> {
  const data = await jsonOrThrow(await fetch(`${API}/api/sources`));
  return data.sources ?? [];
}

export async function deleteSource(id: number): Promise<void> {
  await jsonOrThrow(await fetch(`${API}/api/sources/${id}`, { method: "DELETE" }));
}

export async function search(
  q: string,
  sourceId: number,
  topK = 12,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, source_id: String(sourceId), top_k: String(topK) });
  return jsonOrThrow(await fetch(`${API}/api/search?${params}`));
}
