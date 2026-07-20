"""
Phase 2 processing orchestrator (docs/IMPLEMENTATION.md Phase 2).

Reads every ingested raw document (ingestion/data/raw/*.jsonl), cleans, chunks,
embeds, clusters, and labels — then writes:
  - processing/data/chunks_embedded.jsonl: every chunk + its embedding +
    cluster_id, for Phase 3 to load into Chroma.
  - processing/insights.db: the structured store (theme labels + quotes).

Run manually:
    .venv/Scripts/python.exe processing/run_processing.py
"""

import glob
import hashlib
import json
import os
import sys

from dotenv import load_dotenv

from chunking import chunk_documents
from clean import clean_documents
from cluster import cluster_chunks
from embed import embed_chunks
from label import label_all_clusters
from store import init_db, write_theme

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(PROJECT_ROOT, "ingestion", "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
CHUNKS_OUT_PATH = os.path.join(OUT_DIR, "chunks_embedded.jsonl")

# Resolve SQLITE_DB_PATH against the project root, not the current working
# directory, so running from anywhere lands the DB in the same place (a bare
# relative path in .env otherwise created a nested processing/processing/ copy).
_db_env = os.getenv("SQLITE_DB_PATH", "processing/insights.db")
DB_PATH = _db_env if os.path.isabs(_db_env) else os.path.join(PROJECT_ROOT, _db_env)


def _load_raw_documents() -> list[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))
    return docs


def _assign_chunk_ids(chunks: list[dict]) -> list[dict]:
    for c in chunks:
        basis = f"{c['source_url']}#{c['chunk_index']}"
        c["chunk_id"] = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return chunks


def _prepare_chunks() -> list[dict]:
    """load -> clean -> chunk -> assign chunk_ids (no embedding yet)."""
    print("Loading raw documents...")
    raw_docs = _load_raw_documents()
    print(f"  {len(raw_docs)} raw documents")

    print("Cleaning (dedup, spam filter, language tag)...")
    cleaned = clean_documents(raw_docs)
    print(f"  {len(cleaned)} after cleaning ({len(raw_docs) - len(cleaned)} dropped)")

    print("Chunking...")
    chunks = chunk_documents(cleaned)
    chunks = _assign_chunk_ids(chunks)
    print(f"  {len(chunks)} chunks")
    return chunks


def _load_embedding_cache() -> dict[str, list[float]]:
    """chunk_id -> embedding from a prior run's chunks_embedded.jsonl."""
    if not os.path.exists(CHUNKS_OUT_PATH):
        return {}
    cache = {}
    with open(CHUNKS_OUT_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                if c.get("embedding"):
                    cache[c["chunk_id"]] = c["embedding"]
    return cache


def _embed_incrementally(chunks: list[dict], force_reembed: bool) -> list[dict]:
    """Embed only chunks not already in the cache (keyed by chunk_id) — this is
    what makes a refresh on a grown corpus cost-sublinear (Phase 8 / CLAUDE.md:
    embedding cost scales with NEW documents, not the whole corpus). --reembed
    ignores the cache and re-embeds everything (e.g. after an embedding-model change)."""
    cache = {} if force_reembed else _load_embedding_cache()
    new_chunks = [c for c in chunks if c["chunk_id"] not in cache]
    reused = len(chunks) - len(new_chunks)
    print(f"Embedding (BAAI/bge-m3): {reused} reused from cache, {len(new_chunks)} new to embed...")
    if new_chunks:
        embed_chunks(new_chunks)  # adds 'embedding' in place
    for c in chunks:
        if c["chunk_id"] in cache:
            c["embedding"] = cache[c["chunk_id"]]
    return chunks


def main() -> None:
    force_reembed = "--reembed" in sys.argv
    chunks = _prepare_chunks()
    chunks = _embed_incrementally(chunks, force_reembed)

    # Cluster every run on the full set. Full re-clustering (rather than
    # approximate cluster-prediction for new points) is used deliberately: at this
    # corpus scale it takes seconds and is more stable than incremental assignment,
    # which the architecture designates as the fallback. The cost lever that
    # actually matters for corpus growth — embedding — is already incremental above.
    print("Clustering (PCA -> HDBSCAN)...")
    chunks = cluster_chunks(chunks)
    n_clusters = len({c["cluster_id"] for c in chunks} - {-1})
    n_noise = sum(1 for c in chunks if c["cluster_id"] == -1)
    print(f"  {n_clusters} clusters, {n_noise}/{len(chunks)} chunks marked as noise")

    # Persist chunks (with fresh cluster_ids) so Phase 3's Chroma load and any
    # cluster-based lookup use the current clustering, not a stale cached one.
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(CHUNKS_OUT_PATH, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("Labeling clusters (Groq)...")
    labeled = label_all_clusters(chunks)
    print(f"  {len(labeled)}/{n_clusters} clusters labeled successfully")

    print("Writing structured store...")
    conn = init_db(DB_PATH)
    for label, cluster_chunks_ in labeled:
        theme_id = write_theme(conn, label, cluster_chunks_)
        print(
            f"  theme {theme_id}: \"{label.get('theme')}\" "
            f"({len(cluster_chunks_)} chunks, {label.get('sentiment')}, "
            f"habit={label.get('habit_type')}, frustration={label.get('frustration_type')})"
        )
    conn.close()
    print(f"  wrote {DB_PATH}")


if __name__ == "__main__":
    main()
