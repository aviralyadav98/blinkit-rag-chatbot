"""
Phase 3 — Chroma vector store, behind one interface (docs/ARCHITECTURE.md Sec. 3.3).

Everything that touches Chroma goes through this module, so synthesis and app
code never import chromadb directly. Chroma is the only planned vector store
(no managed-DB swap queued behind it), but keeping the surface small means a
future swap would be a single-file change.

Chunk embeddings are precomputed upstream (processing/embed.py, BAAI/bge-m3,
L2-normalized) and passed in directly — Chroma is not asked to embed anything
on write. Query text, however, must be embedded at query time with the *same*
model, so this module loads bge-m3 lazily for that purpose only.
"""

import math
import os

import chromadb

COLLECTION_NAME = "blinkit_chunks"
EMBED_MODEL_NAME = "BAAI/bge-m3"

# Query embeddings can come from one of two backends, chosen at runtime:
#   1. Local sentence-transformers bge-m3 (default; used for the offline pipeline
#      and any host with the ~2.3GB model + RAM to spare).
#   2. Cloudflare Workers AI's `@cf/baai/bge-m3` — the SAME model, served over a
#      free, no-card HTTP API — used so a lightweight web host never has to load
#      2.3GB. Selected automatically when CF_ACCOUNT_ID + CF_API_TOKEN are set.
# Both are bge-m3, so query vectors stay consistent with the corpus embeddings
# (docs/ARCHITECTURE.md Sec. 3.3). The corpus is L2-normalized and Chroma uses
# cosine, so we normalize the query too regardless of backend.
#
# Creds are read at CALL time (not import time) so that whether .env is loaded
# before or after this module is imported never changes which backend is used.

# Chroma metadata values must be str/int/float/bool — never None. These are the
# metadata fields carried per chunk (docs/ARCHITECTURE.md Sec. 4); None becomes "".
METADATA_FIELDS = ["source_type", "approx_content_date", "category_hint", "cluster_id", "source_url", "language"]

_model = None


def _cf_creds() -> tuple[str | None, str | None]:
    return os.getenv("CF_ACCOUNT_ID"), os.getenv("CF_API_TOKEN")


def _using_cloudflare() -> bool:
    account_id, token = _cf_creds()
    return bool(account_id and token)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def _get_model():
    """Lazy local model. Imported here (not at module top) so a Cloudflare-backed
    web host never pulls in sentence_transformers/torch (~2GB of packages)."""
    global _model
    if _model is None:
        # bge-m3 is cached after first download; offline mode skips the Hub call
        # and its warning. Must be set before sentence_transformers imports it.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def _embed_query_cloudflare(text: str) -> list[float]:
    """Embed one query via Cloudflare Workers AI bge-m3. Normalized client-side to
    match the corpus (cosine is scale-invariant, but we keep vectors comparable)."""
    import requests

    account_id, token = _cf_creds()
    model = os.getenv("CF_EMBED_MODEL", "@cf/baai/bge-m3")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"text": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success", False):
        raise RuntimeError(f"Cloudflare embedding failed: {payload.get('errors')}")
    vec = payload["result"]["data"][0]
    return _l2_normalize(vec)


def embed_query(text: str) -> list[float]:
    """Embed a query with bge-m3 — via Cloudflare if configured, else the local
    model. Same model either way, so query/corpus vectors stay consistent."""
    if _using_cloudflare():
        return _embed_query_cloudflare(text)
    return _get_model().encode([text], normalize_embeddings=True)[0].tolist()


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_client(persist_dir: str | None = None) -> chromadb.ClientAPI:
    # Resolve against the project root, not the current working directory, so
    # callers in app/ vs rag/ vs project root all reach the same store (a bare
    # relative path in .env otherwise points at a nonexistent, empty collection).
    persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_data")
    if not os.path.isabs(persist_dir):
        persist_dir = os.path.join(_PROJECT_ROOT, persist_dir)
    return chromadb.PersistentClient(path=persist_dir)


def get_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def _clean_metadata(chunk: dict) -> dict:
    meta = {}
    for field in METADATA_FIELDS:
        value = chunk.get(field)
        meta[field] = "" if value is None else value
    return meta


def add_chunks(collection, chunks: list[dict], batch_size: int = 500) -> int:
    """Upsert chunks (with their precomputed embeddings) into the collection."""
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        collection.upsert(
            ids=[c["chunk_id"] for c in batch],
            embeddings=[c["embedding"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[_clean_metadata(c) for c in batch],
        )
    return len(chunks)


def query(collection, query_text: str, k: int = 5, where: dict | None = None) -> list[dict]:
    """Semantic search. `where` is an optional Chroma metadata filter.

    Returns a list of {text, metadata, distance} ordered most-similar-first.
    """
    result = collection.query(
        query_embeddings=[embed_query(query_text)],
        n_results=k,
        where=where or None,
    )
    hits = []
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    for doc, meta, dist in zip(docs, metas, dists):
        hits.append({"text": doc, "metadata": meta, "distance": dist})
    return hits
