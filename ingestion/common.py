"""
Shared document shape and dedup helpers for all ingestion sources.

Every scraper (play_store.py, app_store.py, reddit.py, web_crawl.py) normalizes
its actor's raw output into this common shape before it's written anywhere:

    source_type          - "play_store_review" | "app_store_review" | "reddit" |
                            "forum" | "comparison_content"
    source_url            - stable per-item URL, used as the dedup key
    captured_at            - ISO timestamp of when we scraped it (not authored)
    approx_content_date   - when the content was originally posted, if known
    category_hint         - the category this item was sourced under (e.g.
                             "skincare"), if the query/URL made it derivable
    text                  - the raw text content
    extra                 - source-specific fields kept for audit (rating, author, ...)
"""

import json
import os
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_doc(
    source_type: str,
    source_url: str,
    text: str,
    approx_content_date: str | None = None,
    category_hint: str | None = None,
    extra: dict | None = None,
) -> dict:
    return {
        "source_type": source_type,
        "source_url": source_url,
        "captured_at": now_iso(),
        "approx_content_date": approx_content_date,
        "category_hint": category_hint,
        "text": text,
        "extra": extra or {},
    }


def load_existing_urls(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    urls = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            urls.add(json.loads(line)["source_url"])
    return urls


def append_deduped(path: str, docs: list[dict]) -> int:
    """Append docs whose source_url isn't already in the file. Returns count written."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = load_existing_urls(path)
    new_docs = [d for d in docs if d["source_url"] not in existing]
    if not new_docs:
        return 0
    with open(path, "a", encoding="utf-8") as f:
        for doc in new_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return len(new_docs)
