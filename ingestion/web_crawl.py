"""
Forums + comparison content via `requests` + `trafilatura` (free, self-hosted).

Unlike the Apify fallback, this only fetches the given `start_urls` directly —
no recursive crawling of sub-pages. That matches how config.py actually uses
this module today (max_crawl_depth=0 for both forum and comparison-content
jobs): a small, hand-picked list of real URLs, not an open-ended crawl. If a
future job genuinely needs sub-page following, that's the point to add it
(and to reach for the Apify fallback, which already supports it) — not before.
"""

import time

import requests
import trafilatura

from common import make_doc

USER_AGENT = "Mozilla/5.0 (compatible; blinkit-rag-chatbot-research/0.1)"
REQUEST_DELAY_SECS = 2  # politeness delay between fetches, since this is our own direct traffic


def scrape_web_content(
    start_urls: list[str],
    source_type: str,
    max_results: int,
    max_crawl_depth: int = 0,
    category_hint: str | None = None,
) -> list[dict]:
    if source_type not in ("forum", "comparison_content"):
        raise ValueError("source_type must be 'forum' or 'comparison_content'")

    docs = []
    for url in start_urls[:max_results]:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
            downloaded = resp.text
        except requests.RequestException:
            continue

        text = trafilatura.extract(downloaded, url=url, include_comments=True, output_format="txt")
        if not text or not text.strip():
            continue

        meta = trafilatura.extract_metadata(downloaded, default_url=url)
        docs.append(
            make_doc(
                source_type=source_type,
                source_url=url,
                text=text,
                approx_content_date=str(meta.date) if meta and meta.date else None,
                category_hint=category_hint,
                extra={
                    "title": meta.title if meta else None,
                    "author": meta.author if meta else None,
                },
            )
        )
        time.sleep(REQUEST_DELAY_SECS)

    return docs
