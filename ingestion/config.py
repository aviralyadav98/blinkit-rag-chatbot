"""
Phase 1 scrape scope — every value here is a real, verified ID or URL (confirmed
via web search / Apify actor metadata before being added), never a guess.

Kept deliberately small for the first Phase 1 run: enough to prove the pipeline
end-to-end and produce real signal, without triggering CLAUDE.md's cost gate
(scrapes expected to exceed a couple of dollars need sign-off first — this
plan runs to well under $1). Widen categories/volume in a later run once the
shape of this first pass has been reviewed.

Category focus matches docs/PROBLEM_STATEMENT.md Sec. 3: skincare, baby/
parenting, pet, personal finance.
"""

# --- Play Store ---------------------------------------------------------
# com.grofers.customerapp = Blinkit's consumer app package (kept from its
# pre-rebrand "Grofers" name). keywords scope the pull toward category
# mentions rather than bulk-pulling every review (CLAUDE.md: category-first,
# not brand-first bulk pulls).
PLAY_STORE_JOBS = [
    {
        "app_id_or_url": "com.grofers.customerapp",
        "keywords": ["skincare", "baby", "diaper", "pet", "finance", "budget"],
        "max_reviews": 150,
        "category_hint": None,  # mixed categories in one pull; keywords vary per review
    },
]

# --- App Store -----------------------------------------------------------
# 960335206 = "Blinkit: Groceries & more", the consumer app. No keyword
# filter available on this actor (see ingestion/app_store.py docstring), so
# volume is capped instead of query-scoped.
APP_STORE_JOBS = [
    {
        "app_ids": ["960335206"],
        "country": "in",
        "max_items": 150,
        "category_hint": None,
    },
]

# --- Reddit ----------------------------------------------------------------
# Tuned for the PRAW (free) pull during Phase 3 corpus expansion. Changes from
# the first (Apify) pass, which produced heavy noise:
#   - Dropped broad r/india (the main noise source last time). subreddit_urls
#     are now category-native communities confirmed to exist in the earlier
#     scrape results (skincare/beauty/fragrance + personal finance + r/blinkit).
#   - search_terms rewritten to target the thin-signal questions directly:
#     discovery ("where do you buy"), info-needs ("what to know before"),
#     barriers/trust, and first-time category trial.
#   - scrape_comments=True: the "what did you try / what should I know" replies
#     live in comments, not just post bodies — exactly the Q3/Q5 signal.
# The clean.py relevance filter still applies downstream as a second guard.
REDDIT_JOBS = [
    {
        "search_terms": [
            "Blinkit skincare experience",
            "tried skincare Zepto Blinkit worth it",
            "what to know before buying skincare online",
            "Blinkit vs Nykaa skincare authentic",
            "Blinkit beauty products review",
            "first time ordering makeup quick commerce",
            "Blinkit baby products diapers experience",
            "Zepto pet food supplies review",
            "Blinkit new category tried beyond groceries",
            "quick commerce impulse buying what do you order",
        ],
        "subreddit_urls": [
            "r/blinkit",
            "r/IndianSkincareAddicts",
            "r/skincareaddictsindia",
            "r/IndianBeautyTalks",
            "r/IndianBeautyDeals",
            "r/DesiFragranceAddicts",
            "r/personalfinanceindia",
        ],
        "max_posts": 30,
        "category_hint": None,
        "scrape_comments": True,
        "max_comments_per_post": 15,
    },
]

# --- Forums ----------------------------------------------------------------
# DesiDime is a real, active Indian deals/discussion forum. Dedicated
# category-specific forum threads about quick-commerce (pet/parenting/finance)
# did not surface in search — treated as a sparsity finding (CLAUDE.md
# non-negotiable), not papered over with an unrelated URL. Reddit's dedicated
# subreddits (above) carry more of this weight for those categories.
FORUM_JOBS = [
    {
        "start_urls": ["https://www.desidime.com/discussions/blinkit-vs-zepto"],
        "max_results": 5,
        "max_crawl_depth": 0,
        "category_hint": None,
    },
]

# --- Comparison content ----------------------------------------------------
# Real "best app for X" / category-framed content found via search — Quora
# threads on skincare shopping apps, a beauty-on-quick-commerce feature, a
# baby-care-on-quick-commerce feature, and a Blinkit/Zepto/Instamart blog
# comparison. The second batch (Phase 3 corpus expansion) targets the
# thin-signal questions: info-needs (Q5), discovery (Q3), barriers/trust
# (Q2/Q6), and user segments (Q7).
COMPARISON_CONTENT_JOBS = [
    {
        "start_urls": [
            "https://www.quora.com/What-is-the-best-app-for-buying-beauty-care-products",
            "https://www.quora.com/Which-is-better-nykaa-or-Myntra-for-skincare-products",
            "https://www.theestablished.com/self/beauty/the-rise-and-rise-of-beauty-on-indias-quick-commerce-platforms",
            "https://laffaz.com/baby-products-quick-delivery-india-ozi-blinkit-vertical-quick-commerce/",
            "https://nectarbits.com/blog/blinkit-vs-zepto-vs-swiggy-instamart-which-is-better/",
            # --- Phase 3 expansion (targeting thin-signal questions) ---
            # Kept: consumer-oriented content (info-needs, discovery/design, trust).
            # Removed after measurement: 4 B2B/market-analysis docs (confetti
            # "for sellers", metricscart + IBEF market reports, pocketful finance
            # comparison) — they measurably *lowered* retrieval precision by
            # crowding consumer-voice results with market-analysis chunks that are
            # semantically near every question but specifically answer few.
            "https://proskire.in/blogs/news/the-ultimate-guide-to-buying-skincare-products-online-what-you-need-to-know",
            "https://medium.com/design-bootcamp/how-smart-design-makes-you-buy-faster-lessons-from-blinkit-zepto-rapido-minimalist-d7b9439da2bd",
            "https://www.storyboard18.com/brand-marketing/dark-side-of-dark-stores-q-comm-brands-like-blinkit-zepto-are-quickly-losing-consumer-trust-34430.htm",
        ],
        "max_results": 20,
        "max_crawl_depth": 0,
        "category_hint": None,
    },
]
