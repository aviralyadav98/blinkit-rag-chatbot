"""
Phase 1 ingestion orchestrator (docs/IMPLEMENTATION.md Phase 1).

This is the free-tier path (primary): google-play-scraper, Apple's public
reviews RSS feed, official PRAW/Reddit API, and requests+trafilatura — no
Apify spend. See run_ingestion_apify_fallback.py for the paid Apify path,
kept in reserve for whichever source breaks on the free tier.

Stands in for n8n's scheduled workflow for now (n8n's local stand-up is
blocked on a missing Visual Studio Build Tools install — see Phase 0 notes;
revisit wiring this into n8n once that's resolved). Run manually:

    .venv/Scripts/python.exe ingestion/run_ingestion.py

Every source function is deduped on source_url against what's already on disk
(common.append_deduped), so re-running this script is safe and only appends
genuinely new documents — matching the "re-runnable" requirement in
docs/ARCHITECTURE.md. Note: source_url formats differ between the free-tier
and Apify implementations for the same underlying review (different ID
schemes), so switching paths on a corpus already built by the other one may
produce some near-duplicate documents that dedup won't catch.

Query/URL parameters live in config.py, shared by both the free and Apify
paths, kept separate from orchestration logic so the actual scrape scope is
easy to review (CLAUDE.md cost gate applies only to the Apify fallback path —
the free-tier path here has no per-use cost to confirm).
"""

import os

import config
from app_store import scrape_app_store_reviews
from common import append_deduped
from play_store import scrape_play_store_reviews
from reddit import scrape_reddit
from web_crawl import scrape_web_content

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")


def _write(source_type: str, docs: list[dict]) -> None:
    path = os.path.join(DATA_DIR, f"{source_type}.jsonl")
    written = append_deduped(path, docs)
    print(f"[{source_type}] fetched {len(docs)}, wrote {written} new (deduped on source_url)")


def _run_jobs(output_key: str, jobs: list[dict], scrape_fn, **extra_kwargs) -> None:
    """One source failing (e.g. missing credentials) must not take down the rest."""
    for job in jobs:
        try:
            docs = scrape_fn(**job, **extra_kwargs)
            _write(output_key, docs)
        except Exception as e:
            print(f"[{output_key}] SKIPPED: {e}")


def main() -> None:
    _run_jobs("play_store_review", config.PLAY_STORE_JOBS, scrape_play_store_reviews)
    _run_jobs("app_store_review", config.APP_STORE_JOBS, scrape_app_store_reviews)
    _run_jobs("reddit", config.REDDIT_JOBS, scrape_reddit)
    _run_jobs("forum", config.FORUM_JOBS, scrape_web_content, source_type="forum")
    _run_jobs("comparison_content", config.COMPARISON_CONTENT_JOBS, scrape_web_content, source_type="comparison_content")


if __name__ == "__main__":
    main()
