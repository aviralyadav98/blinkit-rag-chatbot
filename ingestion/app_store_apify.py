"""
FALLBACK (paid) — App Store reviews via Apify `thewolves/appstore-reviews-scraper`.

app_store.py (free, direct iTunes RSS reviews feed) is the primary path. This
module is kept for the case where the free path is blocked.

This actor has no keyword/query filter (using its `customMapFunction` for
filtering is explicitly against the actor's terms — it's for reshaping output,
not scoping input). So unlike Play Store, we can't scope this pull to a
category server-side; we cap volume with `maxItems` and rely on Phase 2's
clean step to identify which reviews are actually category-relevant. This
matches CLAUDE.md's note that service-review sources carry weak category
signal — expect this source to contribute less than Reddit/forums.
"""

from apify_common import run_actor_and_get_items
from common import make_doc

ACTOR_ID = "thewolves/appstore-reviews-scraper"


def scrape_app_store_reviews(
    app_ids: list[str],
    country: str,
    max_items: int,
    category_hint: str | None = None,
) -> list[dict]:
    run_input = {
        "appIds": app_ids,
        "country": country,
        "maxItems": max_items,
    }
    items = run_actor_and_get_items(ACTOR_ID, run_input)

    docs = []
    for item in items:
        if item.get("noResults") or not item.get("text"):
            continue  # actor pads output with placeholder rows when a locale has no reviews
        docs.append(
            make_doc(
                source_type="app_store_review",
                source_url=item.get("url") or f"appstore:{item.get('appId')}:{item.get('id')}",
                text=item.get("text") or "",
                approx_content_date=item.get("date"),
                category_hint=category_hint,
                extra={
                    "rating": item.get("score"),
                    "title": item.get("title"),
                    "review_id": item.get("id"),
                    "country": item.get("country"),
                    "app_version": item.get("version"),
                },
            )
        )
    return docs
