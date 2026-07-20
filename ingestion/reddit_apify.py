"""
FALLBACK (paid) — Reddit posts/comments via Apify `harshmaur/reddit-scraper`.

reddit.py (free, official PRAW + Reddit OAuth app) is the primary path. This
module is kept for the case where PRAW/Reddit API access is blocked or
rate-limited below what's needed.

Genuinely category-first: `search_terms` run as keyword searches (e.g. "Blinkit
skincare"), and `subreddit_urls` target category-native communities directly
(parenting/pet/skincare/personal-finance subs) rather than brand mentions.
"""

from apify_common import run_actor_and_get_items
from common import make_doc

ACTOR_ID = "harshmaur/reddit-scraper"


def scrape_reddit(
    search_terms: list[str],
    subreddit_urls: list[str],
    max_posts: int,
    category_hint: str | None = None,
    scrape_comments: bool = False,
    max_comments_per_post: int = 10,
) -> list[dict]:
    run_input = {
        "searchTerms": search_terms,
        "subredditUrls": subreddit_urls,
        "searchPosts": True,
        "searchComments": False,
        "maxPostsCount": max_posts,
        "crawlCommentsPerPost": scrape_comments,
        "maxCommentsPerPost": max_comments_per_post,
        "includeNSFW": False,
    }
    items = run_actor_and_get_items(ACTOR_ID, run_input)

    docs = []
    for item in items:
        is_comment = item.get("dataType") == "comment"
        url = item.get("url") or item.get("postUrl") or item.get("contentUrl")
        text = item.get("body") or item.get("title") or ""
        if not url or not text:
            continue
        docs.append(
            make_doc(
                source_type="reddit",
                source_url=url,
                text=text,
                approx_content_date=item.get("commentCreatedAt") or item.get("createdAt"),
                category_hint=category_hint or item.get("searchTerm"),
                extra={
                    "data_type": item.get("dataType"),
                    "subreddit": item.get("subredditName") or item.get("communityName"),
                    "score": item.get("score") or item.get("commentUpVotes"),
                    "title": item.get("title"),
                    "is_comment": is_comment,
                },
            )
        )
    return docs
