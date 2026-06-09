"""Nyas Postgres access: connection, schema, and small data helpers.

Model (audio-upload era):
  sources   — one row per uploaded audio file (+ its processing status)
  segments  — one row per transcribed chunk (text + timestamps + embedding)
No pgvector on Nyas, so embeddings live in a REAL[] column and we cosine-rank
in numpy.
"""
import psycopg
from psycopg.rows import dict_row
from app.config import DATABASE_URL


def get_conn():
    """Open a connection to Nyas Postgres (IPv4 session pooler, per .env)."""
    return psycopg.connect(DATABASE_URL, connect_timeout=15)


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'audio',
    audio_key    TEXT,                 -- S3 object key of the uploaded file
    content_type TEXT,
    duration_ms  INTEGER,
    status       TEXT NOT NULL DEFAULT 'processing',  -- processing | ready | error
    error        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS segments (
    id         SERIAL PRIMARY KEY,
    source_id  INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    seq        INTEGER NOT NULL,
    start_ms   INTEGER NOT NULL,
    end_ms     INTEGER NOT NULL,
    text       TEXT NOT NULL,
    embedding  REAL[] NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segments_source ON segments(source_id);
"""


def init_schema():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        conn.commit()
    print("✓ schema ready (tables 'sources', 'segments')")


# ---- source helpers ----

def create_source(name: str, audio_key: str, content_type: str, duration_ms: int) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (name, kind, audio_key, content_type, duration_ms, status)
               VALUES (%s,'audio',%s,%s,%s,'processing') RETURNING id;""",
            (name, audio_key, content_type, duration_ms),
        )
        sid = cur.fetchone()[0]
        conn.commit()
    return sid


def set_status(source_id: int, status: str, error: str | None = None):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE sources SET status=%s, error=%s WHERE id=%s;",
                    (status, error, source_id))
        conn.commit()


def insert_segments(source_id: int, rows: list[dict]):
    """rows: [{seq,start_ms,end_ms,text,embedding(list[float])}, ...]"""
    params = [(source_id, r["seq"], r["start_ms"], r["end_ms"], r["text"], r["embedding"])
              for r in rows]
    with get_conn() as conn, conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO segments (source_id, seq, start_ms, end_ms, text, embedding)
               VALUES (%s,%s,%s,%s,%s,%s);""",
            params,
        )
        conn.commit()


def list_sources() -> list[dict]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT s.id, s.name, s.status, s.duration_ms, s.error, s.created_at,
                   COUNT(seg.id) AS segment_count
            FROM sources s LEFT JOIN segments seg ON seg.source_id = s.id
            GROUP BY s.id ORDER BY s.id DESC;
        """)
        return cur.fetchall()


def get_source(source_id: int) -> dict | None:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM sources WHERE id=%s;", (source_id,))
        return cur.fetchone()


def delete_source(source_id: int):
    """Delete a source (segments cascade via FK)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM sources WHERE id=%s;", (source_id,))
        conn.commit()


def latest_ready_source_id() -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM sources WHERE status='ready' ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        return row[0] if row else None


if __name__ == "__main__":
    init_schema()
