"""
Phase 5 — Layer 1 Report Agent (docs/IMPLEMENTATION.md Phase 5, the graded deliverable).

Runs the shared Phase 4 synthesis engine against the 8 fixed research questions
(CLAUDE.md / Problem Statement Sec. 6) and assembles ONE structured report:
per-question answer blocks (grounded answer + verified citations + confidence
signal inline) plus a methodology/validation appendix.

This is a pipeline run, not a hand-authored document — re-running it regenerates
the whole report from the current Chroma collection + structured store, so it
stays valid as the corpus refreshes (Phase 8).

    .venv/Scripts/python.exe app/report_agent.py

Writes docs/INSIGHT_REPORT.md and prints an 8/8 completeness summary.
"""

import os
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))

from retriever import Retriever  # noqa: E402

from confidence import DB_PATH  # noqa: E402
from structured_context import context_for_question  # noqa: E402
from synthesis import MODEL as SYNTHESIS_MODEL  # noqa: E402
from synthesis import synthesize_voted  # noqa: E402

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(_PROJECT_ROOT, "docs", "INSIGHT_REPORT.md")
RETRIEVE_K = 6

# The 8 fixed questions (CLAUDE.md), each with the source-type filter validated in
# Phase 3 (rag/precision_eval.py): frustrations live in app/play-store reviews;
# discovery / barriers / info-needs live in Reddit + comparison content; the
# broad behavioral questions draw on all sources. None = no filter (all sources).
QUESTIONS = [
    ("Why do users repeatedly buy from the same categories?", None),
    ("What prevents users from exploring new categories?", ["reddit", "comparison_content"]),
    ("How do users discover products today?", ["reddit", "comparison_content"]),
    ("What role do habits play in shopping behavior?", None),
    ("What information do users need before trying a new category?", ["reddit", "comparison_content"]),
    ("What frustrations emerge repeatedly?", ["app_store_review", "play_store_review", "reddit"]),
    ("Which user segments are more likely to experiment?", None),
    ("What unmet needs emerge consistently across discussions?", None),
]


def _corpus_stats() -> dict:
    """Read counts from the structured store + Chroma for the methodology appendix."""
    stats = {"themes": 0, "cross_source_themes": 0, "quotes": 0}
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        stats["themes"] = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        stats["cross_source_themes"] = conn.execute(
            "SELECT COUNT(*) FROM themes WHERE cross_source_count >= 2"
        ).fetchone()[0]
        stats["quotes"] = conn.execute("SELECT COUNT(*) FROM quotes").fetchone()[0]
        conn.close()
    return stats


def _render_question_block(idx: int, question: str, result: dict) -> str:
    lines = [f"## Q{idx}. {question}\n"]
    conf = result["confidence"]

    if result["status"] == "insufficient_evidence":
        lines.append("**Finding: Insufficient evidence.**\n")
        vote = f" ({result['vote_record']})" if result.get("vote_record") else ""
        lines.append(f"{result['answer']}{vote}\n")
        lines.append(
            "> This is a reported finding, not an error — the available public "
            "discussion did not contain enough grounded signal to answer this "
            "question without speculation.\n"
        )
        return "\n".join(lines)

    vote = f" · {result['vote_record']}" if result.get("vote_record") else ""
    lines.append(f"{result['answer']}\n")
    lines.append(f"**Confidence:** {conf['level']} — {conf['summary']}{vote}.\n")
    lines.append("**Evidence:**\n")
    for claim in result["claims"]:
        lines.append(f"- {claim['statement']}")
        for cite in claim["citations"]:
            url = cite.get("source_url") or ""
            url_part = f" — [source]({url})" if url.startswith("http") else (f" — `{url}`" if url else "")
            lines.append(f'    - _"{cite["quote"]}"_ — {cite["source_type"]}, {cite["approx_date"]}{url_part}')
    lines.append("")
    return "\n".join(lines)


def _render_appendix(stats: dict, results: list[dict]) -> str:
    answered = sum(1 for r in results if r["status"] == "answered")
    insufficient = len(results) - answered
    high_conf = sum(1 for r in results if r["confidence"].get("level") == "high")
    return f"""## Methodology & Validation Appendix

### Data gathering
Real user language was collected from four public source types via free-tier,
ToS-respecting scrapers (Play Store, Apple's public reviews feed, Reddit, and
`requests`+`trafilatura` for forum/comparison content), orchestrated as a
re-runnable batch job. Sourcing was category-first, not brand-first bulk pulls:
App/Play Store reviews carry weak category signal, so category-native community
discussion and category-framed comparison content carry more of the weight. No
authenticated, paywalled, or private data was scraped.

### Theme identification
Documents were cleaned (near-duplicate removal, spam/low-signal and relevance
filtering, language tagging — Hinglish preserved, not translated), chunked,
embedded locally with `BAAI/bge-m3` (multilingual), and clustered with HDBSCAN.
Each cluster was labeled once by an LLM (Groq) into structured JSON — theme,
sentiment, and PM-facing tags (habit / frustration / discovery / experimentation
propensity) — the only LLM pass over raw text at processing time. The current
corpus yielded **{stats['themes']} themes** ({stats['quotes']} audit quotes).

### Validation approach
- **Groundedness by construction:** every answer is produced only from retrieved
  passages, and every quoted citation is verified to occur verbatim in its cited
  passage before it ships — fabricated or misattributed quotes are dropped, and
  an answer left with no surviving citation is downgraded to insufficient evidence.
- **Retrieval quality:** hand-labeled precision@k on the 8 seed questions
  (recorded in `rag/precision_eval.py`), ~80% at the target boundary.
- **Confidence rule:** a claim is "high confidence" only when supported across
  ≥2 source types; single-source support is labeled as such and never upgraded.

### Known limitations (reported honestly)
- **Corpus thinness.** This is a modest prototype corpus. Only
  **{stats['cross_source_themes']} theme(s)** cross ≥2 source types, so most
  answers are legitimately "single-source" — informative, but not
  cross-triangulated. Denser consumer discussion (broader Reddit coverage) is the
  main lever for stronger cross-source confidence.
- **Sparse questions.** Where public discussion is genuinely thin (e.g. user
  segments), the report returns "insufficient evidence" rather than manufacturing
  a confident answer. This run: **{answered}/8 answered, {insufficient}/8
  insufficient-evidence, {high_conf}/8 high-confidence (≥2 source types).**
"""


def generate_report() -> tuple[str, list[dict]]:
    retriever = Retriever()
    results = []
    for i, (question, source_types) in enumerate(QUESTIONS, 1):
        passages = retriever.retrieve(question, k=RETRIEVE_K, source_types=source_types)
        structured_context = context_for_question(i)
        results.append(synthesize_voted(question, passages, structured_context=structured_context))

    stats = _corpus_stats()
    answered = sum(1 for r in results if r["status"] == "answered")

    header = [
        "# Blinkit Category Cross-Sell — Insight Report",
        "",
        "*Why Blinkit users don't explore new product categories — grounded in real "
        "public user language.*",
        "",
        f"**Generated:** {date.today().isoformat()} · **Completeness:** 8/8 questions addressed "
        f"({answered} answered, {8 - answered} insufficient-evidence) · **Synthesis model:** `{SYNTHESIS_MODEL}`",
        "",
        "Every claim below is traceable to a cited source passage; where evidence is "
        "thin, the report says so explicitly rather than guessing.",
        "",
        "---",
        "",
    ]
    blocks = [_render_question_block(i, q, r) for i, (q, r) in enumerate(zip((q for q, _ in QUESTIONS), results), 1)]
    document = "\n".join(header) + "\n---\n\n".join(blocks) + "\n---\n\n" + _render_appendix(stats, results)
    return document, results


def main() -> int:
    document, results = generate_report()
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(document)

    answered = sum(1 for r in results if r["status"] == "answered")
    insufficient = len(results) - answered
    complete = all(
        (r["status"] == "answered" and r["claims"]) or r["status"] == "insufficient_evidence"
        for r in results
    )
    print(f"Report written to {REPORT_PATH}")
    print(f"Completeness: {len(results)}/8 addressed — {answered} answered, {insufficient} insufficient-evidence")
    for i, (q, _) in enumerate(QUESTIONS, 1):
        r = results[i - 1]
        mark = "answered" if r["status"] == "answered" else "insufficient-evidence"
        print(f"  Q{i}: {mark} ({r['confidence'].get('level')})")
    print(f"\nEXIT CRITERIA (8/8 completeness): {'PASS' if complete else 'FAIL'}")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
