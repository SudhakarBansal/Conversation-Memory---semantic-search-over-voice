// Thin client for the FastAPI backend.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Hit = {
  id: number;
  text: string;
  speaker: string;
  emotion: string;
  sentiment: string;
  score: number;
  dialogue_id: number;
  utterance_id: number;
  audio_url: string;
};

export type SearchResponse = {
  query: string;
  count: number;
  results: Hit[];
};

export type EmotionCount = { emotion: string; count: number };

export async function search(
  q: string,
  topK = 12,
  emotion?: string | null,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, top_k: String(topK) });
  if (emotion) params.set("emotion", emotion);
  const res = await fetch(`${API}/api/search?${params}`);
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}

export async function getEmotions(): Promise<EmotionCount[]> {
  const res = await fetch(`${API}/api/emotions`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.emotions ?? [];
}
