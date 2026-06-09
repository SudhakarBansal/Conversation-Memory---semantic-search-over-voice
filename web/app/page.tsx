"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  uploadSource, listSources, search, deleteSource,
  type Source, type SegHit,
} from "./lib/api";

function mmss(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function Home() {
  const [sources, setSources] = useState<Source[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SegHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const onTimeRef = useRef<(() => void) | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const active = sources.find((s) => s.id === activeId) ?? null;

  const refresh = useCallback(async () => {
    try {
      const list = await listSources();
      setSources(list);
      setActiveId((cur) => cur ?? list.find((s) => s.status === "ready")?.id ?? null);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // poll while anything is still transcribing
  useEffect(() => {
    if (!sources.some((s) => s.status === "processing")) return;
    const t = setTimeout(refresh, 3000);
    return () => clearTimeout(t);
  }, [sources, refresh]);

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const res = await uploadSource(file, name.trim() || file.name);
      setActiveId(res.source_id);
      setResults([]);
      setSearched(false);
      setQuery("");
      setFile(null);
      setName("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await refresh();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function runSearch(q: string) {
    if (!q.trim() || !activeId) return;
    setSearching(true);
    setSearched(true);
    stopAudio();
    try {
      const res = await search(q, activeId, 12);
      setResults(res.results);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function onDelete(s: Source) {
    if (!confirm(`Delete “${s.name}” and its audio? This can't be undone.`)) return;
    stopAudio();
    try {
      await deleteSource(s.id);
      if (activeId === s.id) {
        setActiveId(null);
        setResults([]);
        setSearched(false);
      }
      await refresh();
    } catch {}
  }

  function stopAudio() {
    const a = audioRef.current;
    if (a) {
      a.pause();
      if (onTimeRef.current) {
        a.removeEventListener("timeupdate", onTimeRef.current);
        onTimeRef.current = null;
      }
    }
    setPlayingId(null);
  }

  function togglePlay(hit: SegHit) {
    if (!hit.audio_url) return;
    if (playingId === hit.id) {
      stopAudio();
      return;
    }
    if (!audioRef.current) audioRef.current = new Audio();
    const a = audioRef.current;

    // drop any previous range-stop listener before starting a new moment
    if (onTimeRef.current) {
      a.removeEventListener("timeupdate", onTimeRef.current);
      onTimeRef.current = null;
    }

    const start = hit.start_ms / 1000;
    const end = hit.end_ms / 1000;

    const onTime = () => {
      if (a.currentTime >= end) stopAudio();
    };

    // Seek only once the media can actually seek — setting currentTime before
    // metadata loads is silently ignored, which made playback start at 0:00.
    const seekAndPlay = () => {
      a.currentTime = start;
      a.addEventListener("timeupdate", onTime);
      onTimeRef.current = onTime;
      a.onended = () => setPlayingId(null);
      a.play().then(() => setPlayingId(hit.id)).catch(() => setPlayingId(null));
    };

    if (a.src !== hit.audio_url) {
      a.src = hit.audio_url;
      a.addEventListener("loadedmetadata", seekAndPlay, { once: true });
      a.load();
    } else if (a.readyState >= 1) {
      seekAndPlay();
    } else {
      a.addEventListener("loadedmetadata", seekAndPlay, { once: true });
    }
  }

  const ready = active?.status === "ready";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-5 py-10 sm:py-14">
        {/* Header */}
        <header className="mb-8 text-center">
          <h1 className="bg-gradient-to-r from-fuchsia-400 via-violet-400 to-sky-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl">
            Conversation Memory
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-balance text-sm text-slate-400 sm:text-base">
            Upload any audio — a podcast, a lecture, an interview — and find the
            exact moment by <span className="text-slate-200">meaning</span>, not
            keywords. Transcribed with Whisper, searched by semantic similarity,
            stored on <span className="text-slate-200">Nyas</span>.
          </p>
        </header>

        {/* Upload */}
        <form onSubmit={onUpload} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name this source (optional)"
              className="flex-1 rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2.5 text-sm outline-none placeholder:text-slate-500 focus:border-violet-500"
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-2.5 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white"
            >
              📁 {file ? "Change file" : "Choose audio"}
            </button>
            <span className="max-w-[14rem] truncate text-xs text-slate-400" title={file?.name}>
              {file ? file.name : "no file chosen"}
            </span>
            <button
              type="submit"
              disabled={!file || uploading}
              className="rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:opacity-40"
            >
              {uploading ? "Uploading…" : "Upload & Transcribe"}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Up to 15 minutes. Transcription runs at ~2× realtime, so a 10-min clip
            takes a few minutes.
          </p>
          {uploadError && <p className="mt-2 text-xs text-red-400">{uploadError}</p>}
        </form>

        {/* Source selector */}
        {sources.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">Source:</span>
            {sources.map((s) => (
              <span
                key={s.id}
                className={`inline-flex items-center gap-1 rounded-full border pl-3 pr-1 py-1 text-xs transition ${
                  s.id === activeId
                    ? "border-violet-500 bg-violet-500/15 text-white"
                    : "border-slate-700 text-slate-300 hover:border-slate-600"
                }`}
              >
                <button onClick={() => { setActiveId(s.id); setResults([]); setSearched(false); }}>
                  {s.name}
                  {s.status === "processing" && " ⏳"}
                  {s.status === "error" && " ⚠️"}
                </button>
                <button
                  onClick={() => onDelete(s)}
                  aria-label={`Delete ${s.name}`}
                  title="Delete source"
                  className="flex h-5 w-5 items-center justify-center rounded-full text-slate-500 transition hover:bg-red-500/20 hover:text-red-300"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Processing / error banners */}
        {active?.status === "processing" && (
          <div className="mt-6 flex items-center gap-3 rounded-2xl border border-violet-500/30 bg-violet-500/10 px-4 py-4 text-sm text-violet-200">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-300 border-t-transparent" />
            Transcribing “{active.name}”… this can take a few minutes. The page updates automatically.
          </div>
        )}
        {active?.status === "error" && (
          <div className="mt-6 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            Couldn’t process “{active.name}”: {active.error}
          </div>
        )}

        {/* Search (only when a source is ready) */}
        {ready && (
          <>
            <form
              onSubmit={(e) => { e.preventDefault(); runSearch(query); }}
              className="relative mt-6"
            >
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Search “${active!.name}” by meaning…`}
                className="w-full rounded-2xl border border-slate-700 bg-slate-900/70 px-5 py-4 pr-28 text-base shadow-lg outline-none transition placeholder:text-slate-500 focus:border-violet-500 focus:ring-4 focus:ring-violet-500/20"
              />
              <button
                type="submit"
                disabled={searching || !query.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:opacity-40"
              >
                {searching ? "Searching…" : "Search"}
              </button>
            </form>

            <div className="mt-6 space-y-3">
              {searched && !searching && results.length === 0 && (
                <p className="py-10 text-center text-sm text-slate-500">No moments found.</p>
              )}
              {searching &&
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-20 animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50" />
                ))}
              {!searching &&
                results.map((hit) => {
                  const isPlaying = playingId === hit.id;
                  return (
                    <article
                      key={hit.id}
                      className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 transition hover:border-slate-700"
                    >
                      <div className="flex items-start gap-3">
                        <button
                          onClick={() => togglePlay(hit)}
                          aria-label={isPlaying ? "Pause" : "Play moment"}
                          className={`mt-0.5 flex h-10 w-10 flex-none items-center justify-center rounded-full text-white transition ${
                            isPlaying ? "bg-violet-500" : "bg-violet-600 hover:bg-violet-500"
                          }`}
                        >
                          {isPlaying ? <PauseIcon /> : <PlayIcon />}
                        </button>
                        <div className="min-w-0 flex-1">
                          <p className="text-[15px] leading-snug text-slate-100">{hit.text}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                            <span className="rounded-full border border-slate-700 px-2 py-0.5 font-mono text-slate-300">
                              {mmss(hit.start_ms)}
                            </span>
                            <span className="text-slate-600">·</span>
                            <span className="flex items-center gap-1.5">
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
          </>
        )}

        {/* Empty hint */}
        {sources.length === 0 && (
          <p className="mt-10 text-center text-sm text-slate-500">
            Upload an audio file above to get started.
          </p>
        )}

        <footer className="mt-12 border-t border-slate-800 pt-5 text-center text-xs text-slate-600">
          Whisper (medium) → text embeddings (all-MiniLM-L6-v2) → cosine search (numpy).
          Audio &amp; data on Nyas. No LLM in the loop.
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
