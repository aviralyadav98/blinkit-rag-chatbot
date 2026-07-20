"""
Play Store reviews via `google-play-scraper` (free, scrapes Google's public
review pages directly — no API key, no per-run cost).

No server-side keyword filter is available (unlike the Apify fallback), so
"category-first, not brand-first bulk pulls" (CLAUDE.md) is implemented by
fetching a capped batch sorted newest-first and filtering client-side for
keyword mentions before writing anything out.
"""

from google_play_scraper import Sort, reviews

from common import make_doc


def scrape_play_store_reviews(
    app_id_or_url: str,
    keywords: list[str],
    max_reviews: int,
    category_hint: str | None = None,
    country: str = "in",
) -> list[dict]:
    app_id = app_id_or_url.rsplit("id=", 1)[-1] if "id=" in app_id_or_url else app_id_or_url
    raw_items, _ = reviews(
        app_id,
        lang="en",
        country=country,
        sort=Sort.NEWEST,
        count=max_reviews,
    )

    keywords_lower = [k.lower() for k in keywords]
    docs = []
    for item in raw_items:
        text = item.get("content") or ""
        if keywords_lower and not any(k in text.lower() for k in keywords_lower):
            continue
        review_id = item.get("reviewId")
        at = item.get("at")
        docs.append(
            make_doc(
                source_type="play_store_review",
                source_url=f"https://play.google.com/store/apps/details?id={app_id}&reviewId={review_id}",
                text=text,
                approx_content_date=at.isoformat() if hasattr(at, "isoformat") else at,
                category_hint=category_hint,
                extra={
                    "rating": item.get("score"),
                    "review_id": review_id,
                    "app_version": item.get("reviewCreatedVersion"),
                },
            )
        )
    return docs
