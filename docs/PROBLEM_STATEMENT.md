# RAG-Powered Insight Engine for Blinkit — Category Cross-Sell
### Problem Statement (Part 2)
**Report Agent (primary deliverable) + RAG Chatbot (stretch layer)**

---

## 1. Problem Definition

**What is the problem?**
Evidence about why Blinkit users don't explore new product categories already exists —
scattered across App Store reviews, Play Store reviews, Reddit, community forums, social
conversations, and product/comparison content. It's fragmented, high-volume, continuously
growing, and largely written in Hinglish/code-switched register. Manually reading it
doesn't scale and produces single-reader-biased conclusions. There is currently no system
that (a) turns this corpus into a structured, defensible answer to a fixed set of research
questions, or (b) lets someone interrogate the corpus with a question the original analysis
didn't anticipate.

**Who is facing the problem?**
Growth and Product Managers deciding where to invest cross-category expansion effort;
category and marketing teams needing category-specific trust and discovery gaps before
designing a push; research teams currently doing this via manual thematic coding; and, for
this case study, the analyst building the evidence base and whoever evaluates it.

**What is the business value that will be unlocked?**
A repeatable pipeline that converts unstructured customer voice into a citation-backed
evidence base — collapsing insight generation from weeks of manual reading to a scheduled
run. The primary output (the report) is what makes the Part 1 hypotheses defensible rather
than assumed. The secondary output (the chatbot) makes that same evidence base reusable
for every future question, not just the eight it was built for.

**How will target users benefit?**
They get a polished, cited report answering the core research questions without doing the
reading themselves — and, if they need to go one level deeper on something the report
surfaced, they can ask a follow-up directly against the same evidence base instead of
commissioning new research.

**Why is it urgent now?**
The Part 1 root-cause hypotheses (mental-model anchoring, algorithmic lock-in, trust
non-transfer, need-state asymmetry, etc.) are educated guesses until checked against real
user language. Nothing downstream — solution design, prioritization, stakeholder buy-in —
should be built on unvalidated hypotheses.

---

## 2. Solution Shape — Two Layers, One Backend

| | **Layer 1 — Insight Report Agent** (primary) | **Layer 2 — RAG Chatbot** (stretch) |
|---|---|---|
| What it does | Runs the pipeline against the 8 fixed questions and produces a structured, citation-backed report | Answers ad hoc questions against the same corpus, conversationally, on demand |
| Why it exists | This is what the assignment is graded on — it demonstrates how data was gathered, themes identified, insights generated, and quality validated | A thin conversational layer over the same retrieval + synthesis backend — proves the evidence base is reusable, not a one-shot artifact |
| Priority | Must-have | Nice-to-have — can be cut without reworking Layer 1 |

Both layers share identical ingestion, embedding, clustering, and grounded-synthesis
logic. The only difference is packaging: a generated document vs. a live query loop.

---

## 3. Sourcing Strategy — Getting Category-Level Signal

**The core problem with the naive approach.** Public reviews of Blinkit (App Store, Play
Store, Trustpilot, PissedConsumer, MouthShut) are overwhelmingly about the *service* —
delivery speed, wrong items, refunds, out-of-stock — not about specific products or
categories. Blinkit's own app product cards historically don't even carry a ratings/reviews
element, so there is no rich first-party "product review" surface to scrape. Bulk-scraping
"Blinkit" reviews and hoping category mentions surface is therefore a weak strategy: the
signal for category-exploration behavior is sparse in exactly the sources the brief lists
first.

**The fix is to search differently, not to scrape harder.** Four sourcing moves, mapped to
where category-level signal actually lives:

1. **Category-first search, not app-first.** Query from the category side inward —
   "Blinkit skincare," "quick commerce baby products," "Zepto pet supplies," "Instamart
   electronics" — rather than bulk-pulling brand reviews. People discussing a category
   naturally name which app they use or avoid for it.

2. **Go where the category already lives.** Parenting forums/subreddits, skincare
   communities, pet-owner forums, and personal-finance subs are where "where do you buy X"
   questions get asked, and where quick-commerce apps get named as answers or dismissed as
   options. Richer for habit / discovery / unmet-need questions than app-store reviews.

3. **Mine comparison content as its own source type.** "Best app for X" articles, YouTube
   reviews, and Quora comparisons are inherently category-specific by construction — the
   category framing is already done.

4. **Treat sparsity as a finding, not a gap to paper over.** For genuinely rare
   categories, the honest answer may be "there isn't enough public discussion to say."
   The system must be able to return *insufficient evidence* explicitly rather than
   stretching thin data into a false-confidence claim.

**Source-to-question fit** (which sources are expected to carry signal for which questions):

| Source | Strong signal for | Weak / avoid relying on |
|---|---|---|
| App / Play Store reviews | Frustrations, service friction | Category-exploration reasons |
| Reddit + category subreddits | Discovery, habits, unmet needs, segment differences | Precise frequency (sarcasm-heavy) |
| Category forums (parenting, pets, skincare) | Trust barriers, info-needs before trying a category | App-specific complaints |
| Comparison content (blogs, YouTube, Quora) | Cross-app positioning, category discovery | Emotional depth |

---

## 4. Goals

**Shared backend goal**
Build a retrieval + synthesis pipeline over multi-source, continuously-growing customer
feedback that produces grounded, citation-backed answers — reusable by both the report and
the chatbot.

**Layer 1 goal (primary)**
Automatically generate a structured insight report answering all 8 seed questions, with
evidence quality that holds up to a skeptical stakeholder asking "how do you know?"

**Layer 2 goal (stretch)**
Allow follow-up/exploratory questions against the same corpus without rebuilding ingestion
or retrieval.

**Key metrics**

| Metric | What it checks | Target | Applies to |
|---|---|---|---|
| Groundedness rate | % of claims traceable to a cited source doc | ≥ 95% | Both |
| Retrieval precision@k | % of retrieved chunks actually relevant to the query | ≥ 80% | Both |
| Cross-source coverage | % of "high confidence" themes citing ≥2 source types | ≥ 70% | Both |
| Hallucination rate | Manually audited unsupported-claim rate | < 5% | Both |
| Report completeness | All 8 questions answered with citations | 8/8 | Layer 1 |
| Corpus freshness | Age of most recent ingested doc | Weekly refresh | Both |
| Answer latency | Time to a synthesized answer | < 15 sec | Layer 2 |
| Follow-up coherence | Chatbot correctly uses prior turn as context | Qualitative pass | Layer 2 |

---

## 5. Non-Goals

- Neither layer is a customer-facing feature — internal research/decision-support only.
- Not a real-time streaming/alerting system — scheduled batch ingestion is sufficient.
- Not a replacement for quantitative/transactional analytics — scoped to unstructured text.
- Doesn't scrape authenticated, private, or paywalled data, or violate platform terms.
- Neither layer auto-prioritizes product decisions — output is evidence for a human to
  reason over, not a verdict.
- Not a full regional-language translation product — scoped to English + Hinglish/Hindi as
  they occur naturally in source data.
- Layer 2 is not required to be production-hardened — a working prototype is sufficient.
- Not attempting to manufacture category-level signal where it genuinely doesn't exist —
  sparsity is reported, not filled.

---

## 6. Scope

**Data sources**
App Store reviews · Play Store reviews · Reddit discussions · Community/category forums ·
Social media conversations · Comparison & product-review content

**Must-answer questions (Layer 1 acceptance test; Layer 2 baseline)**
1. Why do users repeatedly buy from the same categories?
2. What prevents users from exploring new categories?
3. How do users discover products today?
4. What role do habits play in shopping behavior?
5. What information do users need before trying a new category?
6. What frustrations emerge repeatedly?
7. Which user segments are more likely to experiment?
8. What unmet needs emerge consistently across discussions?

**Deliverables**
1. **Insight Report** (primary) — a structured document per the 8 questions, each answer
   backed by cited, cross-source evidence, plus a methodology section covering data
   gathering, theme identification, and validation.
2. **RAG Chatbot** (stretch) — a conversational interface over the same backend answering
   the 8 seed questions plus reasonable follow-ups, with the same citation and
   confidence-signaling standard as the report.

---

## 7. Functional Requirements

**Shared backend**
- Ingest and normalize documents from all listed sources.
- Embed and cluster documents; label clusters with theme/sentiment via LLM.
- Retrieve relevant passages per question, across sources — not single-source keyword match.
- Synthesize answers only from retrieved passages, with citation (source type, approximate
  date, short quote) attached to every claim.
- Signal confidence/frequency per theme (e.g., "seen across 40+ reviews and 6 Reddit
  threads" vs. "mentioned once"), and return **insufficient evidence** where warranted.

**Layer 1 — Report Agent**
- Runs against the fixed 8 questions and produces one structured output document.
- Includes a methodology/validation appendix.
- Re-runnable on a schedule as the corpus grows, without manual re-authoring.

**Layer 2 — Chatbot**
- Accepts free-text questions beyond the fixed 8.
- Supports follow-up/drill-down within a conversation.
- Filters by source type, category mentioned, or recency.
- Handles Hinglish/code-switched input.

---

## 8. Non-Functional Requirements / Constraints

- Groundedness over fluency — a shorter, well-cited answer beats a fluent unsupported one.
- Cost-bounded — ingestion + inference cost should scale sub-linearly with corpus growth.
- Auditability — every synthesized claim, in report or chat, must be traceable to source.
- Respects platform terms of use for every scraped source.

---

## 9. Success Criteria / Definition of Done

- **Layer 1 (required):** report answers all 8 questions with citations; a held-out sample
  clears the groundedness/hallucination targets; at least 2 of the Part 1 hypotheses are
  supported or contradicted by real evidence, not re-asserted.
- **Layer 2 (stretch, evaluated only if attempted):** chatbot answers the 8 questions plus
  at least 3 novel follow-ups correctly, with citations and coherent multi-turn context.

---

## 10. Open Questions

- What refresh cadence balances data volume against cost?
- Should confidence scores be exposed numerically, or as qualitative language only?
- How do we avoid over-weighting sarcasm/exaggeration (common on Reddit) as literal
  frequency signal?
- What's the minimum evidence threshold below which the system should return "insufficient
  evidence" rather than a synthesized answer?
- If the chatbot layer is built, who gets query access, and does that change data-handling
  requirements?
- Is the report a one-time deliverable for grading, or the scheduled/re-runnable version
  from day one?
