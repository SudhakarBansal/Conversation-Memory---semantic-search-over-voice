"""
The embedding model — the one piece of real ML here.

An *embedding* turns a piece of text into a fixed-length list of numbers (here,
384 of them) that captures its MEANING. Sentences that mean similar things get
vectors that point in similar directions — even if they share no words. That is
what lets us search by meaning instead of by keyword.

We use a small, free, local model (all-MiniLM-L6-v2) — no API, no cost.
"""
from functools import lru_cache
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import EMBED_MODEL


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    # Loaded once and cached. First call downloads the model (~80 MB) and caches it.
    print(f"loading embedding model: {EMBED_MODEL} ...")
    return SentenceTransformer(EMBED_MODEL)


def embed(texts: list[str]) -> np.ndarray:
    """
    Turn a list of strings into an (N, 384) float32 array of embeddings.

    normalize_embeddings=True scales every vector to length 1. That's a deliberate
    trick: once vectors are unit-length, cosine similarity is just their dot
    product — which makes our search code simple and fast.
    """
    return _model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 50,
    ).astype(np.float32)
