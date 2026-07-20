# Edge Cases — Blinkit Category Cross-Sell RAG System

Derived from `docs/PROBLEM_STATEMENT.md`, `docs/ARCHITECTURE.md`, and `CLAUDE.md`.
Organized by pipeline stage, matching `docs/IMPLEMENTATION.md`'s phases. Each entry:
what can go wrong, why it matters against this project's non-negotiables, and the
expected system behavior. Where the behavior isn't yet decided, it's flagged rather
than assumed — consistent with `CLAUDE.md`'s "propose 2 options and ask" convention.

---

## 1. Ingestion (Phase 1)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Category-first query returns zero results for a rare category (e.g. "Blinkit pet supplies") | System silently has no data for that category and later fabricates a confident answer anyway | Log as a known-sparse category; downstream synthesis must be able to say **insufficient evidence** rather than stretch adjacent categories' data to cover it |
| A source blocks/rate-limits the Apify actor mid-run | Partial, silently-truncated ingestion looks like a complete run | n8n workflow surfaces partial-run status; don't mark corpus as "refreshed" if a source failed outright |
| Scraped content is behind auth/paywall or requires login | Violates ToS / non-goal ("doesn't scrape authenticated, private, or paywalled data") | Actor/query scoped to exclude these up front; if one slips through, drop it at ingestion, don't process it |
| Duplicate documents across runs (same review re-scraped weekly) | Inflates frequency counts, corrupting the confidence signal ("seen across 40+ reviews" becomes meaningless) | Dedup on `source_url` (+ content hash for sources without stable URLs, e.g. some forum posts) before a doc enters processing |
| Same underlying complaint posted by one user across multiple platforms (cross-posting) | Looks like independent cross-source corroboration when it's one voice | Not fully solvable automatically; flag as a known limitation in the report's methodology appendix rather than silently over-crediting cross-source coverage |
| Non-English, non-Hinglish content (e.g. pure Tamil/Bengali review) surfaces in scrape results | Out of scope (English + Hinglish/Hindi only); silently processing garbage embeddings wastes cost and pollutes clusters | Language-detect and drop/flag at ingestion; don't attempt translation (explicit non-goal) |
| Actor cost spikes because a category-first query returns an unexpectedly huge result set | Silent cost overrun | Cap results per query; if a run is projected to exceed the "couple of dollars" threshold, stop and ask before proceeding (`CLAUDE.md` working convention) |
| Source taken down / API deprecated between scheduled runs (e.g. an Apify actor stops working) | Weekly refresh silently stops covering a source with no alert | n8n run should report per-source success/failure, not just overall pipeline success |

---

## 2. Processing — Normalize, Chunk, Embed, Cluster, Label (Phase 2)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Heavy code-switching mid-sentence ("ye app category discover karne me bakwaas hai") | Embedding model or clustering treats it as noise, splitting a real theme across clusters | Accept as expected input shape (not an error); validate embedding quality on Hinglish samples specifically, not just English ones |
| Sarcastic Reddit comment ("wow Blinkit is SO great at suggesting new stuff 🙄") | Read literally, flips sentiment/theme labeling and inflates a frustration's apparent frequency | This is the known open risk flagged in the Problem Statement (Sec. 10); until resolved, treat Reddit-sourced sentiment labels as lower-confidence than App/Play Store review sentiment, and spot-check sarcasm-prone clusters specifically |
| Very short, low-information chunks (one-word App Store reviews: "bad", "ok") | Clutters clusters without adding signal; wastes embedding cost | Filter chunks below a minimum-information threshold before embedding, not after |
| A single mega-thread (long Reddit post + hundreds of comments) dominates a cluster | One thread masquerades as broad consensus; skews frequency count | Weight/cap contribution per source document (e.g. one thread ≠ N independent data points) so frequency reflects distinct voices, not comment count |
| HDBSCAN produces a large "noise" cluster (unclustered points) | Real but rare signal gets discarded silently | Don't drop noise-cluster points outright — they're candidates for exactly the "genuinely rare category" case the system must surface as low-signal rather than ignore |
| Cluster label from Groq is vague or wrong (e.g. mislabels a habit-driven comment as a frustration) | Corrupts the structured store that Layer 1's confidence signal depends on | Manual spot-check step (already in `CLAUDE.md` working conventions) must sample across clusters, not just the largest ones — mislabeled small clusters are easy to miss |
| Incremental clustering (Phase 8) assigns a new document to a stale/wrong existing cluster as the corpus grows | Theme boundaries drift silently over months of weekly refreshes | Periodically (not necessarily weekly) validate incremental-assignment quality against a full re-cluster; re-cluster fully if drift is detected |
| A document is genuinely relevant to multiple categories (e.g. a review mentions both skincare and baby products) | Single-category tagging loses half the signal | `category_hint` should support multiple tags per document rather than forcing one |

---

## 3. RAG Core — Retrieval (Phase 3)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Query for a sparse category returns low-relevance passages just because *something* is always returned by top-k semantic search | Retrieval papers over sparsity instead of surfacing it | Apply a relevance-score floor, not just a fixed k — below-threshold results should count as "nothing found," not be forced into the answer |
| Metadata filter (source type / category / recency) eliminates all candidates | Empty result silently passed to synthesis, which may hallucinate to fill the gap | Retrieval layer returns an explicit empty-result signal; synthesis must map that to **insufficient evidence**, never to invention |
| Near-duplicate chunks (same review scraped twice before Phase 1 dedup catches it, or paraphrased reposts) dominate top-k | Retrieved "evidence" looks like several sources agreeing when it's the same text twice | De-duplicate/diversify at retrieval time (e.g. cap near-identical chunks in a single result set) so retrieved evidence reflects distinct voices |
| A question's language mixes Hinglish and English in ways the embedding model handles asymmetrically | Retrieval quality differs by question phrasing, not by actual corpus content | Validate precision@k separately on English-phrased and Hinglish-phrased versions of the same underlying question |
| Recency filter requested (Layer 2) but most matching content predates the filter window | Empty/thin result set | Same as above — return explicit insufficient-evidence/no-recent-data signal rather than falling back to stale data unlabeled |

---

## 4. Shared Synthesis Engine (Phase 4)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Retrieved passages weakly support a claim but don't fully back the confident phrasing an LLM defaults to | Groundedness/hallucination targets (≥95% / <5%) silently fail | Prompt must constrain phrasing to match evidence strength — "some users mention X" vs. "users consistently report X" — not just constrain *content* |
| A theme has plenty of raw mentions but they're all from one source type | Could be mislabeled "high confidence" if frequency alone is used as the signal | Confidence logic must check the ≥2-source-type rule explicitly, independent of raw count — a single-source theme is flagged as such even at high volume |
| Retrieved passages directly contradict each other (e.g. some reviews say delivery speed builds trust, others say it doesn't matter for category adoption) | A synthesized answer picks one side silently | Surface the contradiction explicitly in the answer rather than resolving it invisibly — this is itself a finding |
| Question is answerable in general but not for the specific sub-slice asked (e.g. asks about a category with near-zero mentions, worded as if data exists) | Model pattern-matches to the general case, ignoring the actual data gap | Insufficient-evidence path must trigger per-question, based on what was actually retrieved, not on how the question is phrased |
| Citation quote is technically present in a passage but taken out of context in a way that changes its meaning | Passes an automated "quote exists in source" check while still being misleading | Manual audit sampling (Phase 6) must read quotes in surrounding context, not just verify string presence |
| Confidence signal input (structured store) and retrieval input (vector store) drift out of sync after incremental updates | Report cites "seen across 40+ reviews" for a theme whose vector-store evidence has since changed | Structured store and vector store should be refreshed together in the same pipeline run, never independently |

---

## 5. Layer 1 — Report Agent (Phase 5)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| One or more of the 8 fixed questions returns insufficient evidence | Report completeness metric (8/8) looks like a failure when honesty is actually the correct outcome | Report completeness means "8/8 questions addressed," where an explicit, well-justified insufficient-evidence answer counts as addressed — distinct from a missing/blank section |
| Two scheduled runs (a week apart) produce meaningfully different answers to the same question | Looks inconsistent to a stakeholder without context | Methodology appendix should note corpus size/date range per run so shifts are explainable, not just visible |
| A Part 1 hypothesis is neither clearly supported nor contradicted by available evidence | Success criteria (≥2 hypotheses addressed) gets forced into a false "supported" or "contradicted" verdict | Allow and explicitly state a third outcome — "insufficient evidence to evaluate this hypothesis" — rather than forcing a binary verdict |

---

## 6. Layer 2 — Chatbot (Phase 7, stretch)

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Follow-up question implicitly references prior turn ("what about for skincare specifically?") | Retrieval treats it as a stand-alone query and misses the intended scope | Query expansion must fold prior-turn context into the retrieval query, not just into the final prompt |
| User asks a question entirely outside the corpus's scope (e.g. asks about delivery-time SLAs, a service topic the corpus wasn't built to answer authoritatively at category-level) | Model answers from general world knowledge instead of the corpus | Same grounding rule as Layer 1 applies — no corpus support means insufficient evidence, even for on-brand-sounding questions |
| Conversation runs long enough that early turns fall out of any context window | Multi-turn coherence degrades silently mid-conversation | Define and test a max coherent conversation depth rather than assuming unlimited follow-up depth |
| User asks a question in heavy Hinglish that the system must both understand and retrieve against | Layer 2's Hinglish requirement is only validated on synthesis, not on the user-input side | Test the full loop (Hinglish question → retrieval → synthesis), not just Hinglish source documents |
| Latency target (<15s) is missed because a follow-up triggers a much larger retrieval scope than the fixed 8 questions ever did | Silent SLA miss on novel questions specifically | Cap retrieval scope per query regardless of question novelty; if a broader search is genuinely needed, that's a design decision to surface, not to let happen silently |

---

## 7. Cross-Cutting

| Edge case | Risk if unhandled | Expected behavior |
|---|---|---|
| Corpus grows to a size where full re-embedding/re-clustering becomes cost-prohibitive | Violates the sub-linear-cost non-functional requirement | Incremental processing (Phase 8) is the default; full reprocessing is an explicit, approved exception, not a routine fallback |
| A source changes its terms of service after ingestion already started scraping it | Continuing to scrape violates the ToS non-negotiable retroactively | Ingestion should be checked against current ToS at each scheduled run, not only at initial setup |
| Vector store and structured store fall out of sync (e.g. Phase 8 updates one but a run fails partway before updating the other) | Confidence signals and retrieved evidence describe two different corpus states | Treat a partial pipeline run as a failed run for both stores — don't publish a report or serve chat answers from a half-updated state |
| Report or chatbot output is shared outside its internal research/decision-support scope | Violates non-goal (not a customer-facing feature); output could be read as a product decision rather than evidence for one | Report/chatbot output should carry a visible reminder that it's evidence for human judgment, not a verdict (Problem Statement Sec. 5 non-goal) |
