"""
Phase 2 step 2 — Normalize + chunk (docs/IMPLEMENTATION.md Phase 2).

Most ingested items (reviews, Reddit posts) are already short and need no
splitting. Only long-form content (comparison-content articles) benefits from
chunking — this splits on paragraph boundaries first, falling back to a
character-window split for single huge paragraphs, so chunks stay
retrieval-friendly without cutting mid-sentence where avoidable.
"""

CHUNK_TARGET_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150


def _split_long_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= CHUNK_TARGET_CHARS:
            current = f"{current}\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > CHUNK_TARGET_CHARS:
                # single paragraph too long on its own - character-window split
                start = 0
                while start < len(para):
                    end = start + CHUNK_TARGET_CHARS
                    chunks.append(para[start:end])
                    start = end - CHUNK_OVERLAP_CHARS
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks or [text]


def chunk_documents(docs: list[dict]) -> list[dict]:
    """Splits long documents into multiple chunk records; short ones pass through as-is.

    Each output record is a shallow copy of its source doc with `text` replaced
    by the chunk text and a `chunk_index` field added.

    Chunks are deduplicated on normalized text *across all documents*: clean.py
    dedups whole documents before chunking, but cross-posted long docs (e.g. the
    same Reddit roundup reposted to several subreddits, or a repeated template
    block within one post) produce identical chunks that only chunk-level dedup
    catches.
    """
    import re

    seen_chunk_texts = set()
    chunks = []
    for doc in docs:
        text = doc.get("text", "")
        pieces = _split_long_text(text) if len(text) > CHUNK_TARGET_CHARS else [text]
        for i, piece in enumerate(pieces):
            norm = re.sub(r"\s+", " ", piece.strip().lower())
            if norm in seen_chunk_texts:
                continue
            seen_chunk_texts.add(norm)
            chunk = dict(doc)
            chunk["text"] = piece
            chunk["chunk_index"] = i
            chunks.append(chunk)
    return chunks
