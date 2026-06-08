"use client";

import { useEffect, useRef, useState } from "react";
import { search, getEmotions, type Hit, type EmotionCount } from "./lib/api";
import { emotionStyle } from "./lib/emotions";

const EXAMPLES = [
  "food being delicious",
  "someone panicking or freaking out",
  "a romantic confession of love",
  "angry about being betrayed",
  "saying goodbye to a friend",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [emotions, setEmotions] = useState<EmotionCount[]>([]);
  const [emotion, setEmotion] = useState<string | null>(null);

  // one shared audio element; clicking a card plays its clip, pausing any other
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);

  useEffect(() => {
    getEmotions().then(setEmotions).catch(() => {});
  }, []);

  async function runSearch(q: string, emo: string | null = emotion) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    stopAudio();
    try {
      const res = await search(q, 12, emo);
      setResults(res.results);
    } catch {
      setError("Couldn't reach the search API. Is the backend running on :8000?");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function onExample(q: string) {
    setQuery(q);
    runSearch(q);
  }

  function onEmotionToggle(e: string) {
    const next = emotion === e ? null : e;
    setEmotion(next);
    if (searched && query.trim()) runSearch(query, next);
  }

  function stopAudio() {
    audioRef.current?.pause();
    setPlayingId(null);
  }

  function togglePlay(hit: Hit) {
    if (playingId === hit.id) {
      stopAudio();
      return;
    }
    if (!audioRef.current) audioRef.current = new Audio();
    const a = audioRef.current;
    a.src = hit.audio_url;
    a.onended = () => setPlayingId(null);
    a.play().then(() => setPlayingId(hit.id)).catch(() => setPlayingId(null));
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-5 py-10 sm:py-16">
        {/* Header */}
        <header className="mb-8 text-center">
          <h1 className="bg-gradient-to-r from-fuchsia-400 via-violet-400 to-sky-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
            Conversation Memory
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-balance text-sm text-slate-400 sm:text-base">
            Search <span className="text-slate-200">1,108 real conversation moments</span> by{" "}
            <span className="text-slate-200">meaning</span>, not keywords. No LLM — just the actual
            words people said, ranked by semantic similarity and played from{" "}
            <span className="text-slate-200">Nyas</span> storage.
          </p>
        </header>

        {/* Search bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runSearch(query);
          }}
          className="relative"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Describe a moment… e.g. “someone is nervous about a date”"
            className="w-full rounded-2xl border border-slate-700 bg-slate-900/70 px-5 py-4 pr-28 text-base shadow-lg outline-none transition placeholder:text-slate-500 focus:border-violet-500 focus:ring-4 focus:ring-violet-500/20"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:opacity-40"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        {/* Example queries */}
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="self-center text-xs text-slate-500">Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => onExample(ex)}
              className="rounded-full border border-slate-700 bg-slate-900/50 px-3 py-1 text-xs text-slate-300 transition hover:border-violet-500/60 hover:text-white"
            >
              {ex}
            </button>
          ))}
        </div>

        {/* Emotion filter */}
        {emotions.length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">Filter emotion:</span>
            {emotions.map(({ emotion: e, count }) => {
              const st = emotionStyle(e);
              const active = emotion === e;
              return (
                <button
                  key={e}
                  onClick={() => onEmotionToggle(e)}
                  className={`rounded-full border px-2.5 py-1 text-xs capitalize transition ${st.chip} ${
                    active ? "ring-2 ring-white/40" : "opacity-70 hover:opacity-100"
                  }`}
                >
                  {st.emoji} {e} <span className="opacity-60">{count}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Results */}
        <div className="mt-8 space-y-3">
          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {!error && searched && !loading && results.length === 0 && (
            <p className="py-10 text-center text-sm text-slate-500">No moments found.</p>
          )}

          {loading &&
            Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-24 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50"
              />
            ))}

          {!loading &&
            results.map((hit) => {
              const st = emotionStyle(hit.emotion);
              const isPlaying = playingId === hit.id;
              return (
                <article
                  key={hit.id}
                  className="group rounded-2xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-slate-700"
                >
                  <div className="flex items-start gap-3">
                    {/* Play button */}
                    <button
                      onClick={() => togglePlay(hit)}
                      aria-label={isPlaying ? "Pause" : "Play clip"}
                      className={`mt-0.5 flex h-10 w-10 flex-none items-center justify-center rounded-full text-white transition ${
                        isPlaying ? "bg-violet-500" : "bg-violet-600 hover:bg-violet-500"
                      }`}
                    >
                      {isPlaying ? <PauseIcon /> : <PlayIcon />}
                    </button>

                    <div className="min-w-0 flex-1">
                      <p className="text-[15px] leading-snug text-slate-100">“{hit.text}”</p>

                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-medium text-slate-300">{hit.speaker}</span>
                        <span className={`rounded-full border px-2 py-0.5 capitalize ${st.chip}`}>
                          {st.emoji} {hit.emotion}
                        </span>
                        <span className="text-slate-600">·</span>
                        {/* similarity score */}
                        <span className="flex items-center gap-1.5 text-slate-400">
                          <span className="inline-block h-1.5 w-16 overflow-hidden rounded-full bg-slate-700">
                            <span
                              className="block h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400"
                              style={{ width: `${Math.round(hit.score * 100)}%` }}
                            />
                          </span>
                          {hit.score.toFixed(2)} match
                        </span>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
        </div>

        {/* Footer */}
        <footer className="mt-12 border-t border-slate-800 pt-5 text-center text-xs text-slate-600">
          Embeddings: all-MiniLM-L6-v2 · Similarity: cosine (numpy) · Data &amp; audio: Nyas
          Postgres &amp; storage · Dataset: MELD
        </footer>
      </div>
    </div>
  );
}

function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function PauseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </svg>
  );
}
