"""
FastAPI backend for Conversation Memory.

On startup it loads the whole embedding index into memory once (1108 x 384 is
tiny). Each /api/search request embeds the query and ranks by cosine similarity,
then attaches a presigned Nyas-storage URL so the browser can play each clip.

Run:  ./.venv/bin/uvicorn app.api:app --reload --port 8000
"""
from contextlib import asynccontextmanager
from collections import Counter

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app import storage
from app.search import load_all, rank

# In-memory index, populated at startup.
INDEX = {"records": [], "matrix": None}


def _refresh():
    records, matrix = load_all()
    INDEX["records"], INDEX["matrix"] = records, matrix
    return len(records)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    n = _refresh()
    print(f"✓ index loaded: {n} utterances")
    yield


app = FastAPI(title="Conversation Memory", lifespan=lifespan)

# Allow the Next.js dev server (localhost:3000) to call us during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "count": len(INDEX["records"])}


@app.get("/api/emotions")
def emotions():
    """Emotion labels + counts — for the filter dropdown in the UI."""
    counts = Counter(r["emotion"] for r in INDEX["records"])
    return {"emotions": [{"emotion": e, "count": c} for e, c in counts.most_common()]}


@app.get("/api/search")
def search(
    q: str = Query(..., description="meaning-based query"),
    top_k: int = Query(10, ge=1, le=50),
    emotion: str | None = Query(None, description="optional emotion filter"),
):
    hits = rank(q, INDEX["records"], INDEX["matrix"], top_k=top_k, emotion=emotion)
    results = [{
        "id": h["id"],
        "text": h["text"],
        "speaker": h["speaker"],
        "emotion": h["emotion"],
        "sentiment": h["sentiment"],
        "score": round(h["score"], 4),
        "dialogue_id": h["dialogue_id"],
        "utterance_id": h["utterance_id"],
        "audio_url": storage.presigned_url(h["audio_key"]),
    } for h in hits]
    return {"query": q, "count": len(results), "results": results}
