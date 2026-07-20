"""
Fallback ingestion orchestrator — same job as run_ingestion.py, but routed
through the paid Apify actors instead of the free-tier scrapers. Use this only
if a free-tier source is blocked (e.g. Google/Apple change their page format,
or Reddit API access isn't set up yet) and the corresponding CLAUDE.md cost
gate has been cleared for the paid re-run.

    .venv/Scripts/python.exe ingestion/run_ingestion_apify_fallback.py
"""

import os

import config
from app_store_apify import scrape_app_store_reviews
from common import append_deduped
from play_store_apify import scrape_play_store_reviews
from reddit_apify import scrape_reddit
from web_crawl_apify import scrape_web_content

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")


def _write(source_type: str, docs: list[dict]) -> None:
    path = os.path.join(DATA_DIR, f"{source_type}.jsonl")
    written = append_deduped(path, docs)
    print(f"[{source_type}] fetched {len(docs)}, wrote {written} new (deduped on source_url)")


def _run_jobs(output_key: str, jobs: list[dict], scrape_fn, **extra_kwargs) -> None:
    """One source failing must not take down the rest."""
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
