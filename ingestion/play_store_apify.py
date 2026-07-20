"""
FALLBACK (paid) — Play Store reviews via Apify `neatrat/google-play-store-reviews-scraper`.

play_store.py (free, google-play-scraper) is the primary path. This module is
kept for the case where the free path is blocked (e.g. Google changes the
review page format faster than google-play-scraper's maintainers can patch).

The actor takes one app at a time and has no free-text query — "category-first,
not brand-first bulk pulls" (CLAUDE.md) is implemented here via the `keywords`
filter, scoping the pull to reviews that mention a category rather than
bulk-pulling every review for the app.
"""

from apify_common import run_actor_and_get_items
from common import make_doc

ACTOR_ID = "neatrat/google-play-store-reviews-scraper"


def scrape_play_store_reviews(
    app_id_or_url: str,
    keywords: list[str],
    max_reviews: int,
    category_hint: str | None = None,
) -> list[dict]:
    run_input = {
        "appIdOrUrl": app_id_or_url,
        "maxReviews": max_reviews,
        "keywords": keywords,
        "uniqueOnly": True,
    }
    items = run_actor_and_get_items(ACTOR_ID, run_input)

    docs = []
    for item in items:
        review_id = item.get("reviewId")
        docs.append(
            make_doc(
                source_type="play_store_review",
                source_url=f"https://play.google.com/store/apps/details?id={app_id_or_url}&reviewId={review_id}",
                text=item.get("body") or "",
                approx_content_date=item.get("date"),
                category_hint=category_hint,
                extra={
                    "rating": item.get("rating"),
                    "review_id": review_id,
                    "language": item.get("language"),
                    "app_version": item.get("appVersion"),
                },
            )
        )
    return docs
