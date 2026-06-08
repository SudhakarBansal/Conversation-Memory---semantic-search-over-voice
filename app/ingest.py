"""
Ingest pipeline: MELD dev split -> embeddings + Nyas Postgres + Nyas storage.

Steps:
  1. Read data/dev.csv (transcript + speaker + emotion + ids).
  2. Keep rows whose .flac actually exists on disk.
  3. Embed every transcript in one batch (sentence-transformers).
  4. Upload each .flac to Nyas storage (skipping ones already there).
  5. Insert/refresh one row per utterance in Nyas Postgres.

Run:
  python -m app.db                      # create the table
  python -m app.ingest                  # full ingest (text + audio)
  python -m app.ingest --no-audio       # text/embeddings only (fast, submittable)
  python -m app.ingest --limit 50       # quick test on 50 rows
"""
import argparse
import csv
import os

from app.db import get_conn, init_schema
from app.embed import embed
from app import storage

CSV_PATH = "data/dev.csv"
AUDIO_DIR = "data/dev"

# The MELD CSV is UTF-8 but the original Windows-1252 punctuation got mangled into
# C1 control chars (e.g. U+0092 instead of ’). Map that 0x80–0x9F range back to the
# real cp1252 character (’ “ ” – — … etc.) so transcripts read cleanly.
_C1_FIX = {}
for _cp in range(0x80, 0xA0):
    try:
        _C1_FIX[_cp] = bytes([_cp]).decode("cp1252")
    except UnicodeDecodeError:
        pass


def clean(s: str) -> str:
    return s.translate(_C1_FIX).strip()


def load_rows(limit: int | None):
    """Read the CSV, keeping only rows that have a matching audio file."""
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d, u = r["Dialogue_ID"], r["Utterance_ID"]
            fname = f"dia{d}_utt{u}.flac"
            if not os.path.exists(os.path.join(AUDIO_DIR, fname)):
                continue  # the 1 missing clip, etc.
            rows.append({
                "dialogue_id": int(d),
                "utterance_id": int(u),
                "speaker": clean(r["Speaker"]),
                "emotion": r["Emotion"],
                "sentiment": r["Sentiment"],
                "text": clean(r["Utterance"]),
                "audio_key": fname,
            })
            if limit and len(rows) >= limit:
                break
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-audio", action="store_true", help="skip uploading clips")
    ap.add_argument("--limit", type=int, default=None, help="only N rows (testing)")
    args = ap.parse_args()

    init_schema()

    rows = load_rows(args.limit)
    print(f"rows to ingest: {len(rows)}")

    # --- 3. Embed all transcripts at once ---
    embeddings = embed([r["text"] for r in rows])
    print(f"✓ embedded {len(rows)} utterances -> {embeddings.shape}")

    # --- 4. Upload audio (skip files already in the bucket) ---
    if not args.no_audio:
        already = storage.list_keys()
        to_upload = [r for r in rows if r["audio_key"] not in already]
        print(f"uploading {len(to_upload)} clips ({len(rows) - len(to_upload)} already there)...")
        for i, r in enumerate(to_upload, 1):
            storage.upload_file(os.path.join(AUDIO_DIR, r["audio_key"]), r["audio_key"])
            if i % 100 == 0 or i == len(to_upload):
                print(f"  uploaded {i}/{len(to_upload)}")
    else:
        print("skipping audio upload (--no-audio)")

    # --- 5. Insert rows in ONE batched call (idempotent upsert) ---
    # executemany is pipelined by psycopg3 — one round-trip batch instead of
    # 1108 separate ones, so this is seconds not minutes.
    params = [
        (r["dialogue_id"], r["utterance_id"], r["speaker"], r["emotion"],
         r["sentiment"], r["text"], r["audio_key"], vec.tolist())
        for r, vec in zip(rows, embeddings)
    ]
    sql = """
        INSERT INTO utterances
            (dialogue_id, utterance_id, speaker, emotion, sentiment, text, audio_key, embedding)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (dialogue_id, utterance_id) DO UPDATE SET
            speaker=EXCLUDED.speaker, emotion=EXCLUDED.emotion,
            sentiment=EXCLUDED.sentiment, text=EXCLUDED.text,
            audio_key=EXCLUDED.audio_key, embedding=EXCLUDED.embedding;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(sql, params)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM utterances;")
        total = cur.fetchone()[0]
    print(f"✓ inserted/updated {len(params)} rows")

    print(f"\n🎉 ingest done — {total} utterances in Nyas Postgres.")


if __name__ == "__main__":
    main()
