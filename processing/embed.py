"""
Phase 2 step 3 — Embed (docs/IMPLEMENTATION.md Phase 2, CLAUDE.md decided architecture).

`BAAI/bge-m3` via sentence-transformers: free, local, multilingual (handles
Hinglish/code-switched text), no API key. First call downloads the model
(~2.3GB) — that download, not the embedding itself, is what's slow.
"""

from sentence_transformers import SentenceTransformer

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model


def embed_chunks(chunks: list[dict], batch_size: int = 16) -> list[dict]:
    """Adds an `embedding` field (list[float]) to each chunk dict.

    Embeddings are L2-normalized so downstream Euclidean-distance clustering
    (processing/cluster.py) behaves equivalently to cosine similarity, which
    is what these sentence embeddings are meant to be compared with.
    """
    model = get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts, batch_size=batch_size, show_progress_bar=True, normalize_embeddings=True
    )
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()
    return chunks
