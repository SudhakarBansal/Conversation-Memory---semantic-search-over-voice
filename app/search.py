"""
Semantic search — the payoff.

We load every stored embedding into one numpy matrix, embed the query the same
way, and rank utterances by COSINE SIMILARITY.

Cosine similarity measures the angle between two vectors (ignoring length): 1.0 =
same direction (same meaning), 0 = unrelated, -1 = opposite. Because we stored
unit-length (normalized) vectors, cosine similarity is simply the dot product —
so ranking is one matrix-vector multiply. No LLM, no pgvector, instant.
"""
import numpy as np
from app.db import get_conn
from app.embed import embed


def load_all():
    """Pull every utterance + its embedding from Postgres into memory.

    Returns (records, matrix): a list of dict rows (without the raw embedding)
    and an aligned (N, 384) float32 matrix of unit vectors.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, dialogue_id, utterance_id, speaker, emotion, sentiment,
                   text, audio_key, embedding
            FROM utterances;
        """)
        cols = [c.name for c in cur.description]
        records = [dict(zip(cols, row)) for row in cur.fetchall()]
    matrix = np.array([r.pop("embedding") for r in records], dtype=np.float32)
    return records, matrix


def rank(query: str, records, matrix, top_k: int = 10, emotion: str | None = None):
    """Rank pre-loaded records against a query. Pure function — no DB/model state
    beyond the (cached) embedding model. Returns records with a 'score' added."""
    if not records:
        return []
    q = embed([query])[0]          # (384,) unit vector
    scores = matrix @ q            # (N,) cosine similarity = dot product
    out = []
    for i in np.argsort(-scores):  # highest score first
        rec = records[i]
        if emotion and rec["emotion"] != emotion:
            continue
        out.append({**rec, "score": float(scores[i])})
        if len(out) >= top_k:
            break
    return out


def search(query: str, top_k: int = 10, emotion: str | None = None):
    """Convenience for one-off CLI use: load from DB, then rank."""
    records, matrix = load_all()
    return rank(query, records, matrix, top_k, emotion)


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "someone is panicking"
    print(f"query: {q!r}\n")
    for r in search(q, top_k=5):
        print(f"  {r['score']:.3f}  [{r['speaker']}/{r['emotion']}]  {r['text']}")
