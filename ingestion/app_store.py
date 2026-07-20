"""
App Store reviews via Apple's public customer-reviews RSS feed (free, no key):

    https://itunes.apple.com/rss/customerreviews/id={app_id}/page={page}/sortby=mostrecent/json

No keyword filter is available (same limitation as the Apify fallback), so
volume is capped and Phase 2's clean step identifies category-relevant reviews.

Known issue (verified, not app-specific): as of this writing, this endpoint
returns an empty feed for both Blinkit (960335206) and even very high-review
apps like Facebook (284882215) and Instagram (389801252), across both `us`
and `in` locales. This appears to be a broad reliability regression on
Apple's side, not a bug in this scraper or a Blinkit-specific gap — the
`app_store_apify.py` fallback hit the same wall via a different technique,
returning `{"noResults": true}`. Kept implemented because the endpoint is
still the correct free approach and may recover; sparsity here should be
reported as a genuine finding (CLAUDE.md non-negotiable), not silently retried
into a false signal.
"""

import requests

from common import make_doc

BASE_URL = "https://itunes.apple.com/rss/customerreviews/id={app_id}/page={page}/sortby=mostrecent/json"


def _fetch_page(app_id: str, page: int) -> list[dict]:
    resp = requests.get(BASE_URL.format(app_id=app_id, page=page), timeout=30)
    resp.raise_for_status()
    return resp.json().get("feed", {}).get("entry", [])


def scrape_app_store_reviews(
    app_ids: list[str],
    country: str,
    max_items: int,
    category_hint: str | None = None,
) -> list[dict]:
    docs = []
    for app_id in app_ids:
        page = 1
        while len(docs) < max_items and page <= 10:  # Apple caps this feed at 10 pages
            entries = _fetch_page(app_id, page)
            if not entries or (page == 1 and len(entries) <= 1):
                break  # entry[0] is app metadata, not a review, when reviews exist at all
            for entry in entries[1:]:
                text = entry.get("content", {}).get("label", "")
                if not text:
                    continue
                review_id = entry.get("id", {}).get("label", "")
                docs.append(
                    make_doc(
                        source_type="app_store_review",
                        source_url=review_id or f"appstore:{app_id}:{page}:{len(docs)}",
                        text=text,
                        approx_content_date=entry.get("updated", {}).get("label"),
                        category_hint=category_hint,
                        extra={
                            "rating": entry.get("im:rating", {}).get("label"),
                            "title": entry.get("title", {}).get("label"),
                            "app_version": entry.get("im:version", {}).get("label"),
                            "country": country,
                        },
                    )
                )
                if len(docs) >= max_items:
                    break
            page += 1
    return docs
