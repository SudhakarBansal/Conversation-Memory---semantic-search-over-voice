"""
Transcription with faster-whisper (medium model, CPU/int8).

Decodes an audio file once (to 16 kHz mono), checks the duration cap, then runs
Whisper. Whisper natively returns segments with start/end timestamps — exactly
the chunks we embed and later seek to during playback.
"""
from functools import lru_cache
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

MODEL_SIZE = "medium"
SAMPLE_RATE = 16000
MAX_DURATION_MS = 15 * 60 * 1000  # 15-minute cap

# Whisper's native segments are sentence/phrase-level (~2-5 s) — too granular to
# carry a whole thought, which hurts semantic search. We merge consecutive
# segments into ~CHUNK_TARGET_MS windows before embedding, so each searchable
# chunk holds enough context (and the play button seeks to its start).
CHUNK_TARGET_MS = 25_000


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    print(f"loading faster-whisper '{MODEL_SIZE}' (cpu/int8) ...")
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def probe_duration_ms(path: str) -> int:
    """Decode audio and return its duration in ms (also used for the cap check)."""
    audio = decode_audio(path, sampling_rate=SAMPLE_RATE)
    return int(len(audio) / SAMPLE_RATE * 1000)


def transcribe(path: str) -> tuple[int, list[dict]]:
    """
    Transcribe an audio file into timestamped segments.

    Returns (duration_ms, segments) where each segment is
    {seq, start_ms, end_ms, text}. Raises ValueError if over the duration cap.
    """
    audio = decode_audio(path, sampling_rate=SAMPLE_RATE)
    duration_ms = int(len(audio) / SAMPLE_RATE * 1000)
    if duration_ms > MAX_DURATION_MS:
        raise ValueError(
            f"audio is {duration_ms/60000:.1f} min; the limit is "
            f"{MAX_DURATION_MS/60000:.0f} min"
        )

    seg_iter, _info = _model().transcribe(audio, beam_size=1)

    # Merge Whisper's short native segments into ~CHUNK_TARGET_MS windows so each
    # searchable chunk carries a whole thought. We keep the first segment's
    # start_ms, extend end_ms, and join the text; flush once the window is long
    # enough, then flush any remainder.
    chunks: list[dict] = []
    cur: dict | None = None
    for s in seg_iter:
        text = s.text.strip()
        if not text:
            continue
        start_ms = int(s.start * 1000)
        end_ms = int(s.end * 1000)
        if cur is None:
            cur = {"start_ms": start_ms, "end_ms": end_ms, "text": text}
        else:
            cur["end_ms"] = end_ms
            cur["text"] += " " + text
        if cur["end_ms"] - cur["start_ms"] >= CHUNK_TARGET_MS:
            chunks.append(cur)
            cur = None
    if cur is not None:
        chunks.append(cur)

    segments = [{"seq": i, **c} for i, c in enumerate(chunks)]
    return duration_ms, segments
