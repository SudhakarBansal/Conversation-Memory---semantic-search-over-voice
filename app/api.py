"""
FastAPI backend — upload audio, transcribe with Whisper, search by meaning.

Flow:
  POST /api/sources (audio file)  -> save + upload to Nyas, create source row
                                     (status=processing), kick off a background
                                     thread that transcribes + embeds + stores,
                                     returns {source_id} immediately.
  GET  /api/sources               -> list sources with status + segment counts.
  GET  /api/sources/{id}          -> one source (poll this for status).
  GET  /api/search?q&source_id    -> rank that source's segments by meaning;
                                     each hit carries start/end ms + audio_url.

Run:  ./.venv/bin/uvicorn app.api:app --reload --port 8000
"""
import os
import shutil
import tempfile
import threading
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import db, fetch_url, storage
from app.embed import embed
from app.search import load_segments, rank
from app.transcribe import transcribe, probe_duration_ms, MAX_DURATION_MS

app = FastAPI(title="Conversation Memory")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serialize transcriptions so two uploads don't thrash the CPU at once.
_transcribe_lock = threading.Lock()


@app.on_event("startup")
def _startup():
    db.init_schema()


# ---------- processing (runs in a background thread) ----------

def _process(source_id: int, local_path: str):
    try:
        with _transcribe_lock:
            duration_ms, segs = transcribe(local_path)
        if not segs:
            db.set_status(source_id, "error", "no speech found")
            return
        vectors = embed([s["text"] for s in segs])
        for s, v in zip(segs, vectors):
            s["embedding"] = v.tolist()
        db.insert_segments(source_id, segs)
        db.set_status(source_id, "ready")
        print(f"✓ source {source_id}: {len(segs)} segments ready")
    except Exception as e:  # noqa: BLE001 — surface any failure as source error
        db.set_status(source_id, "error", str(e)[:500])
        print(f"✗ source {source_id} failed: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


def _process_url(source_id: int, url: str, key: str):
    """Download audio from a URL, store it, then index it (same pipeline as upload)."""
    try:
        local_path = fetch_url.download_audio(url)
    except Exception as e:  # noqa: BLE001
        db.set_status(source_id, "error", f"download failed: {str(e)[:300]}")
        print(f"✗ source {source_id} download failed: {e}")
        return
    try:
        storage.upload_file(local_path, key, content_type="audio/mpeg")
    except Exception as e:  # noqa: BLE001
        db.set_status(source_id, "error", f"upload failed: {str(e)[:300]}")
        if os.path.exists(local_path):
            os.remove(local_path)
        return
    _process(source_id, local_path)  # transcribe + embed + store + mark ready; removes temp


# ---------- endpoints ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sources")
async def create_source(file: UploadFile = File(...), name: str = Form(...)):
    # save upload to a temp file
    suffix = os.path.splitext(file.filename or "")[1] or ".audio"
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as out:
        shutil.copyfileobj(file.file, out)

    # duration cap — reject early, before creating anything
    try:
        duration_ms = probe_duration_ms(tmp)
    except Exception:
        os.remove(tmp)
        raise HTTPException(400, "could not read that audio file")
    if duration_ms > MAX_DURATION_MS:
        os.remove(tmp)
        raise HTTPException(
            400, f"audio is {duration_ms/60000:.1f} min; limit is {MAX_DURATION_MS/60000:.0f} min"
        )

    # upload original file to Nyas storage (for playback)
    key = f"uploads/{uuid.uuid4().hex}{suffix}"
    content_type = file.content_type or "application/octet-stream"
    storage.upload_file(tmp, key, content_type=content_type)

    source_id = db.create_source(name.strip() or file.filename or "Untitled",
                                 key, content_type, duration_ms)

    threading.Thread(target=_process, args=(source_id, tmp), daemon=True).start()
    return {"source_id": source_id, "status": "processing", "duration_ms": duration_ms}


class UrlSource(BaseModel):
    url: str
    name: str | None = None


@app.post("/api/sources/url")
def create_source_from_url(body: UrlSource):
    """Ingest audio from a YouTube / media URL (yt-dlp). Probes duration for the
    cap check first, then downloads + transcribes in a background thread."""
    url = body.url.strip()
    if not url:
        raise HTTPException(400, "url is required")

    # cheap metadata probe — enforce the cap before any heavy download
    try:
        duration_ms, title = fetch_url.probe_url(url)
    except Exception:
        raise HTTPException(400, "couldn't read audio from that link")
    if duration_ms > MAX_DURATION_MS:
        raise HTTPException(
            400, f"audio is {duration_ms/60000:.1f} min; limit is {MAX_DURATION_MS/60000:.0f} min"
        )

    key = f"uploads/{uuid.uuid4().hex}.mp3"
    name = (body.name or "").strip() or title
    source_id = db.create_source(name, key, "audio/mpeg", duration_ms)

    threading.Thread(target=_process_url, args=(source_id, url, key), daemon=True).start()
    return {"source_id": source_id, "status": "processing", "duration_ms": duration_ms, "title": title}


@app.get("/api/sources")
def get_sources():
    return {"sources": db.list_sources()}


@app.get("/api/sources/{source_id}")
def get_source(source_id: int):
    src = db.get_source(source_id)
    if not src:
        raise HTTPException(404, "source not found")
    return src


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int):
    src = db.get_source(source_id)
    if not src:
        raise HTTPException(404, "source not found")
    if src.get("audio_key"):
        try:
            storage.delete_object(src["audio_key"])
        except Exception as e:  # noqa: BLE001 — don't block DB delete on a storage hiccup
            print(f"warning: could not delete audio {src['audio_key']}: {e}")
    db.delete_source(source_id)  # segments cascade
    return {"deleted": source_id}


@app.get("/api/sources/{source_id}/audio")
def get_audio(source_id: int, request: Request):
    """Serve the source's audio with HTTP Range support so the browser can seek.

    Nyas storage doesn't honor Range (a presigned URL is non-seekable, so
    playback would always start at 0:00). We fetch the object once (cached) and
    answer Range requests ourselves with 206 Partial Content.
    """
    src = db.get_source(source_id)
    if not src or not src.get("audio_key"):
        raise HTTPException(404, "source not found")

    data = storage.get_bytes(src["audio_key"])
    total = len(data)
    content_type = src.get("content_type") or "audio/mpeg"
    rng = request.headers.get("range")

    if rng and rng.startswith("bytes="):
        spec = rng.split("=", 1)[1].split(",")[0].strip()
        start_s, _, end_s = spec.partition("-")
        if start_s == "":  # suffix range: bytes=-N -> last N bytes
            length = int(end_s)
            start = max(0, total - length)
            end = total - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else total - 1
        end = min(end, total - 1)
        if start > end:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{total}"})
        chunk = data[start:end + 1]
        return Response(
            chunk,
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{total}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(chunk)),
            },
        )

    return Response(
        data,
        media_type=content_type,
        headers={"Accept-Ranges": "bytes", "Content-Length": str(total)},
    )


@app.get("/api/search")
def search(
    request: Request,
    q: str = Query(..., min_length=1),
    source_id: int | None = Query(None),
    top_k: int = Query(10, ge=1, le=50),
):
    sid = source_id or db.latest_ready_source_id()
    if sid is None:
        return {"query": q, "source_id": None, "count": 0, "results": []}

    src = db.get_source(sid)
    # Serve audio through our own Range-capable endpoint (Nyas URLs aren't seekable).
    audio_url = f"{str(request.base_url).rstrip('/')}/api/sources/{sid}/audio" \
        if src and src.get("audio_key") else None

    records, matrix = load_segments(sid)
    hits = rank(q, records, matrix, top_k=top_k)
    results = [{
        "id": h["id"],
        "seq": h["seq"],
        "text": h["text"],
        "start_ms": h["start_ms"],
        "end_ms": h["end_ms"],
        "score": round(h["score"], 4),
        "audio_url": audio_url,
    } for h in hits]
    return {"query": q, "source_id": sid, "count": len(results), "results": results}
