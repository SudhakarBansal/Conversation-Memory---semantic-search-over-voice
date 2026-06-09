"""
Semantic search over a source's segments.

Load the source's segment embeddings into one numpy matrix, embed the query the
same way, rank by cosine similarity (= dot product, since vectors are unit
length). No LLM, no pgvector — one matrix-vector multiply.
"""
import numpy as np
from psycopg.rows import dict_row
from app.db import get_conn
from app.embed import embed


def load_segments(source_id: int):
    """Return (records, matrix) for one source. records keep text+timestamps."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT id, seq, start_ms, end_ms, text, embedding
               FROM segments WHERE source_id=%s ORDER BY seq;""",
            (source_id,),
        )
        records = cur.fetchall()
    if not records:
        return [], np.zeros((0, 384), dtype=np.float32)
    matrix = np.array([r.pop("embedding") for r in records], dtype=np.float32)
    return records, matrix


def rank(query: str, records, matrix, top_k: int = 10):
    if not records:
        return []
    q = embed([query])[0]
    scores = matrix @ q
    out = []
    for i in np.argsort(-scores)[:top_k]:
        out.append({**records[i], "score": float(scores[i])})
    return out


def search(query: str, source_id: int, top_k: int = 10):
    records, matrix = load_segments(source_id)
    return rank(query, records, matrix, top_k)
