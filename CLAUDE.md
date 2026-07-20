# Blinkit Category Cross-Sell — RAG Insights Chatbot

## What this project is
A Retrieval-Augmented-Generation chatbot that answers behavioral research questions
about why Blinkit users don't explore new product categories, grounded in real user
language scraped from App Store reviews, Play Store reviews, Reddit, community forums,
social media, and product reviews.

This is an **internal research/decision-support tool**, not a customer-facing feature.

Full problem statement, goals, non-goals, and success criteria: `docs/PROBLEM_STATEMENT.md`.
Read that file before implementing anything — it defines "done."

## Two layers, one backend
- **Layer 1 — Insight Report Agent (PRIMARY):** runs the pipeline against the 8 fixed
  questions and produces a structured, citation-backed report with a methodology appendix.
  This is the graded deliverable — build it first.
- **Layer 2 — RAG Chatbot (STRETCH):** a thin conversational layer over the *same* backend
  for ad hoc follow-up questions. Do not rebuild ingestion/retrieval for it. Cut it before
  compromising Layer 1 if time runs short.

## Sourcing strategy (important — don't naively bulk-scrape brand reviews)
App/Play Store reviews are about the SERVICE (delivery, refunds, wrong items), not about
category-exploration behavior. Blinkit product cards historically lack a reviews surface,
so there's little first-party product-review data. Get category-level signal by:
1. **Category-first search** ("Blinkit skincare", "quick commerce baby products", "Zepto
   pet supplies") — not app-first bulk pulls.
2. **Category-native communities** — parenting/pet/skincare forums & subreddits, personal-
   finance subs, where "where do you buy X" gets asked.
3. **Comparison content** — "best app for X" blogs, YouTube, Quora (category-framed already).
4. **Report sparsity as a finding** — where public discussion is genuinely thin, return
   "insufficient evidence," never a false-confidence synthesized claim.

## The 8 questions this MUST answer (acceptance test)
1. Why do users repeatedly buy from the same categories?
2. What prevents users from exploring new categories?
3. How do users discover products today?
4. What role do habits play in shopping behavior?
5. What information do users need before trying a new category?
6. What frustrations emerge repeatedly?
7. Which user segments are more likely to experiment?
8. What unmet needs emerge consistently across discussions?

Every answer must cite its source (source type + approximate date + short quote) and
signal confidence (e.g. "seen across 40+ reviews and 6 Reddit threads" vs. "mentioned once").

## Architecture (decided — don't re-litigate without discussion)
- **Ingestion (primary, free)**: `google-play-scraper` (Play Store), Apple's public
  reviews RSS feed (App Store — currently unreliable on Apple's side, verified
  across multiple apps, not just Blinkit), official Reddit API via PRAW (a free
  "script" app registered at reddit.com/prefs/apps), and `requests` + `trafilatura`
  for forums/comparison-content URLs. No per-use cost.
- **Ingestion (fallback, paid)**: the same four sources via Apify actors —
  `neatrat/google-play-store-reviews-scraper`, `thewolves/appstore-reviews-scraper`,
  `harshmaur/reddit-scraper`, `apify/website-content-crawler` — kept in reserve for
  whichever free source gets blocked. `ingestion/run_ingestion.py` (free) is the
  default entry point; `ingestion/run_ingestion_apify_fallback.py` is the paid one.
- **Orchestration**: n8n for scheduled scraping + batch processing loops.
- **Embeddings + clustering**: embed all documents with `BAAI/bge-m3` (free, local,
  multilingual — handles Hinglish/code-switched text; no API key), cluster (HDBSCAN),
  then use Groq (`llama-3.3-70b-versatile`) to label clusters and tag theme/sentiment
  as structured JSON — don't run freeform LLM reads over the whole raw corpus, it's
  inconsistent and expensive at scale.
- **Vector store / RAG**: Chroma only — free, self-hosted, sufficient for this
  project's scale. No planned swap to a managed vector DB.
- **Synthesis**: Groq API (`llama-3.3-70b-versatile`), prompted to answer only from
  retrieved passages and to cite every claim. No answer should assert something the
  retrieved context doesn't support.
- **Structured store**: a simple table (SQLite/Airtable) tracking theme × frequency ×
  source × severity, separate from the vector store, for reporting/audit.

## Non-negotiable requirements
- **Groundedness over fluency.** A shorter, well-cited answer beats a fluent one with
  unsupported claims. Target ≥95% of claims traceable to a cited source; hallucination
  rate <5% on manual audit.
- **Cross-source triangulation.** A theme is "high confidence" only if it independently
  appears across ≥2 source types. Say so explicitly when a theme is single-source.
  Target ≥70% of high-confidence themes crossing 2+ sources.
- **Return "insufficient evidence" when warranted.** For rare categories with thin public
  discussion, the honest answer is that there isn't enough signal — never stretch sparse
  data into a confident-sounding claim. Sparsity is itself a reportable finding.
- **Full traceability.** Every synthesized claim must be click-through-able to the raw
  source document. No answer without citations.
- **Handles Hinglish / code-switched text** in both source documents and user queries.
- **Respect platform terms of use** for every scraped source. Don't scrape
  authenticated/paywalled/private data.
- **Not real-time.** Scheduled batch refresh (weekly default) is sufficient — don't
  build streaming ingestion unless asked.

## Working conventions
- Ask before running a scrape that will cost more than a couple of dollars (applies
  to the Apify fallback path — the free-tier ingestion path has no per-use cost).
- Ask before changing the vector DB, embedding model, or synthesis prompt's grounding
  rules — these are the trust-critical parts of the system.
- Make minimal, focused changes; don't refactor unrelated code in the same commit.
- When a design choice isn't specified above, propose 2 options and ask rather than
  picking silently — this is a research tool, and silent assumptions here produce
  ungrounded "insights" that look authoritative and aren't.
- Manually spot-check a sample of any new theme-tagging output for precision before
  treating it as ground truth.

## Repo layout
```
docs/            problem statement, requirements, open questions
ingestion/       free-tier scrapers (primary) + Apify actor calls (fallback),
                 n8n workflow exports
processing/      embedding, clustering, theme/sentiment tagging
rag/             vector store setup, retrieval logic, chunking
app/             chat interface / API that ties retrieval + Groq synthesis together
.env.example     required environment variables (copy to .env, never commit .env)
```

## Environment
See `.env.example` for required keys (Groq API, Reddit script-app credentials, Apify
token for the fallback path). Chroma, the `bge-m3` embedding model, Play Store, App
Store, and web-crawl ingestion all run locally and need no API key. Never commit `.env`.
