"""
Phase 3 — load Phase 2's embedded chunks into Chroma (docs/IMPLEMENTATION.md Phase 3).

Reads processing/data/chunks_embedded.jsonl and upserts every chunk (embedding
+ text + metadata) into the Chroma collection. Idempotent: upsert keyed on
chunk_id means re-running after a fresh Phase 2 run replaces existing rows
rather than duplicating them.

    .venv/Scripts/python.exe rag/load_chroma.py
"""

import json
import os
import re

from dotenv import load_dotenv

from vector_store import add_chunks, get_client, get_collection

load_dotenv()

CHUNKS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "processing", "data", "chunks_embedded.jsonl"
)


def _load_chunks() -> list[dict]:
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _dedup_by_text(chunks: list[dict]) -> list[dict]:
    """Drop chunks whose normalized text already appeared. Lossless for retrieval —
    identical text has an identical embedding, so a duplicate hit only ever wastes
    a top-k slot. (Cross-posted Reddit roundups produce many identical chunks; the
    document-level dedup in processing/clean.py runs before chunking and misses
    these.)"""
    seen = set()
    deduped = []
    for c in chunks:
        norm = re.sub(r"\s+", " ", c["text"].strip().lower())
        if norm in seen:
            continue
        seen.add(norm)
        deduped.append(c)
    return deduped


# Founder/self-promotion marketing posts (someone pitching a tool/startup/service)
# pass the category keyword filter but are not consumer voice about Blinkit
# category behavior — they were the top crowders on the "what info do users need"
# and "which users experiment" questions. Applied to Reddit only, where this
# pattern occurs; reviews and hand-picked comparison URLs don't carry it.
SELF_PROMO_PATTERNS = [
    "i build a tool", "i built a tool", "i made a tool", "i've built", "i have built",
    "pipeline i run", "tool i built", "tool called", "my tool", "my startup",
    "we're building", "we are building", "i'm building", "dm me", "link in bio",
    "check out my", "sign up", "waitlist", "join the waitlist", "impuls8",
    # analytics-jargon markers of the same D2C market-analysis thread whose
    # non-promo chunks (e.g. "the useful metric isn't the brand count...") are
    # about founder market research, not consumer voice about Blinkit categories.
    "brand count", "ask count", "micro-niche", "micro niches", "d2c brand",
]


def _drop_self_promotion(chunks: list[dict]) -> list[dict]:
    kept = []
    for c in chunks:
        if c.get("source_type") == "reddit":
            low = c["text"].lower()
            if any(p in low for p in SELF_PROMO_PATTERNS):
                continue
        kept.append(c)
    return kept


def build_collection(verbose: bool = False) -> int:
    """Rebuild the Chroma collection from the portable chunks_embedded.jsonl into
    whatever CHROMA_PERSIST_DIR points at, using the running chromadb version.

    This is the version-agnostic path the web host uses: the committed
    rag/chroma_data binary index is written by a specific chromadb version and a
    different host version may not read it, but the JSONL (precomputed embeddings
    as plain JSON) is portable, so rebuilding from it always yields an index the
    current chromadb can read. Same dedup + self-promo filter as a normal load, so
    retrieval is identical."""
    chunks = _load_chunks()
    deduped = _dedup_by_text(chunks)
    filtered = _drop_self_promotion(deduped)
    if verbose:
        print(f"  {len(chunks)} chunks -> {len(deduped)} after dedup -> {len(filtered)} after promo filter")

    client = get_client()
    # Rebuild from scratch so removed duplicates don't linger from a prior load.
    try:
        client.delete_collection(get_collection(client).name)
    except Exception:
        pass
    collection = get_collection(client)
    return add_chunks(collection, filtered)


def main() -> None:
    print(f"Loading embedded chunks from {CHUNKS_PATH}...")
    n = build_collection(verbose=True)
    client = get_client()
    print(f"  upserted {n} chunks (total in collection: {get_collection(client).count()})")


if __name__ == "__main__":
    main()
