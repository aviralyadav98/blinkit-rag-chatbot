"""
Reddit posts/comments via the official Reddit API (PRAW), free tier.

More ToS-compliant than scraping Reddit's pages directly (CLAUDE.md
non-negotiable: respect platform terms for every scraped source) — this goes
through Reddit's own OAuth API rather than an unofficial scraper.

Genuinely category-first: `search_terms` run as keyword searches across all of
Reddit (e.g. "Blinkit skincare"), and `subreddit_urls` target specific
communities directly. Note: a subreddit's `.new()` listing is NOT filtered by
search_terms — it pulls that community's recent posts wholesale, same
trade-off observed with the Apify version (see docs/IMPLEMENTATION.md Phase 1
notes on Reddit signal quality). Keep subreddit_urls to genuinely
category-native communities, not broad general-interest ones, to avoid noise.
"""

from praw_common import get_client

from common import make_doc


def _submission_to_doc(submission, category_hint: str | None) -> dict | None:
    text = submission.selftext or submission.title
    if not text:
        return None
    return make_doc(
        source_type="reddit",
        source_url=f"https://www.reddit.com{submission.permalink}",
        text=text,
        approx_content_date=str(submission.created_utc),
        category_hint=category_hint,
        extra={
            "data_type": "post",
            "subreddit": str(submission.subreddit),
            "score": submission.score,
            "title": submission.title,
            "is_comment": False,
        },
    )


def _comment_to_doc(comment, submission, category_hint: str | None) -> dict | None:
    if not comment.body or comment.body in ("[deleted]", "[removed]"):
        return None
    return make_doc(
        source_type="reddit",
        source_url=f"https://www.reddit.com{comment.permalink}",
        text=comment.body,
        approx_content_date=str(comment.created_utc),
        category_hint=category_hint,
        extra={
            "data_type": "comment",
            "subreddit": str(submission.subreddit),
            "score": comment.score,
            "title": submission.title,
            "is_comment": True,
        },
    )


def scrape_reddit(
    search_terms: list[str],
    subreddit_urls: list[str],
    max_posts: int,
    category_hint: str | None = None,
    scrape_comments: bool = False,
    max_comments_per_post: int = 10,
) -> list[dict]:
    reddit = get_client()
    seen_ids = set()
    docs = []

    def _handle_submission(submission):
        if submission.id in seen_ids:
            return
        seen_ids.add(submission.id)
        doc = _submission_to_doc(submission, category_hint)
        if doc:
            docs.append(doc)
        if scrape_comments:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list()[:max_comments_per_post]:
                cdoc = _comment_to_doc(comment, submission, category_hint)
                if cdoc:
                    docs.append(cdoc)

    for term in search_terms:
        for submission in reddit.subreddit("all").search(term, sort="new", limit=max_posts):
            _handle_submission(submission)

    for sub_url in subreddit_urls:
        name = sub_url.replace("https://www.reddit.com/r/", "").replace("r/", "").strip("/")
        for submission in reddit.subreddit(name).new(limit=max_posts):
            _handle_submission(submission)

    return docs
