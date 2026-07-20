"""
FALLBACK (paid) — Forums + comparison content via Apify `apify/website-content-crawler`.

web_crawl.py (free, requests + trafilatura) is the primary path. This module
is kept for pages that need JS rendering or heavier anti-bot handling than a
plain HTTP fetch can manage.

Unlike the other three actors, this one has no search/keyword mode — it only
crawls from explicit start URLs (and their sub-pages, bounded by max_crawl_depth
and max_results). It's used for two of the four source categories from
`docs/PROBLEM_STATEMENT.md` Sec. 3: category forums and comparison content
("best app for X" blogs/Quora); which one a given call produces is determined
entirely by which real URLs are passed in as `start_urls` — there is no
category-first *query* possible here, only category-first *URL selection*
made ahead of time.
"""

from apify_common import run_actor_and_get_items
from common import make_doc

ACTOR_ID = "apify/website-content-crawler"


def scrape_web_content(
    start_urls: list[str],
    source_type: str,
    max_results: int,
    max_crawl_depth: int = 1,
    category_hint: str | None = None,
) -> list[dict]:
    if source_type not in ("forum", "comparison_content"):
        raise ValueError("source_type must be 'forum' or 'comparison_content'")

    run_input = {
        "startUrls": [{"url": u} for u in start_urls],
        "crawlerType": "playwright:adaptive",
        "maxCrawlDepth": max_crawl_depth,
        "maxResults": max_results,
        "proxyConfiguration": {"useApifyProxy": True},
        "respectRobotsTxtFile": True,
        "saveMarkdown": False,
    }
    items = run_actor_and_get_items(ACTOR_ID, run_input)

    docs = []
    for item in items:
        text = item.get("text") or ""
        if not text.strip():
            continue
        metadata = item.get("metadata") or {}
        crawl = item.get("crawl") or {}
        docs.append(
            make_doc(
                source_type=source_type,
                source_url=item.get("url"),
                text=text,
                approx_content_date=crawl.get("loadedTime"),
                category_hint=category_hint,
                extra={
                    "title": metadata.get("title"),
                    "author": metadata.get("author"),
                    "language": metadata.get("languageCode"),
                },
            )
        )
    return docs
