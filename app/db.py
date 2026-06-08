"""Nyas Postgres access: a connection helper + the schema."""
import psycopg
from app.config import DATABASE_URL


def get_conn():
    """Open a connection to Nyas Postgres (IPv4 session pooler, per .env)."""
    return psycopg.connect(DATABASE_URL, connect_timeout=15)


# One row per utterance. No pgvector on Nyas yet, so the embedding lives in a
# plain REAL[] (float array) column; we load them into numpy for cosine search.
SCHEMA = """
CREATE TABLE IF NOT EXISTS utterances (
    id            SERIAL PRIMARY KEY,
    dialogue_id   INTEGER NOT NULL,
    utterance_id  INTEGER NOT NULL,
    speaker       TEXT,
    emotion       TEXT,
    sentiment     TEXT,
    text          TEXT NOT NULL,
    audio_key     TEXT NOT NULL,        -- S3 object key, e.g. 'dia0_utt0.flac'
    embedding     REAL[] NOT NULL,      -- 384-dim meaning vector
    UNIQUE (dialogue_id, utterance_id)  -- lets us re-run ingest safely
);
"""


def init_schema():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        conn.commit()
    print("✓ schema ready (table 'utterances')")


if __name__ == "__main__":
    init_schema()
