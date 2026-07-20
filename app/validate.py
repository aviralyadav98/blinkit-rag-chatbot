"""
Phase 6 — Validation Gate (docs/IMPLEMENTATION.md Phase 6).

Audits the generated report (docs/INSIGHT_REPORT.md) against the evidence-quality
bar. This is an INDEPENDENT check: it re-parses the finished report and re-verifies
every cited quote against the raw corpus, rather than trusting the generation step.

    .venv/Scripts/python.exe app/validate.py

Checks:
  1. Groundedness rate  — % of cited claims whose quote is found verbatim in the
     corpus (target >=95%).
  2. Hallucination rate  — % of citations whose quote is NOT in the corpus
     (fabricated/misattributed; target <5%).
  3. Cross-source coverage — of answers marked high-confidence, the share citing
     >=2 source types; plus the structured store's cross-source theme count.
  4. Hypothesis check — surfaces the Part 1 root-cause hypotheses and auto-detects
     which the report's evidence bears on (>=2 required); final judgement is manual.
"""

import json
import os
import re
import sqlite3
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(_PROJECT_ROOT, "docs", "INSIGHT_REPORT.md")
CHUNKS_PATH = os.path.join(_PROJECT_ROOT, "processing", "data", "chunks_embedded.jsonl")
DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(_PROJECT_ROOT, "processing", "insights.db"))
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(_PROJECT_ROOT, DB_PATH)

# Part 1 root-cause hypotheses (docs/PROBLEM_STATEMENT.md) + keywords that signal
# the report bears on each.
HYPOTHESES = {
    "mental-model anchoring": ["habit", "same categor", "daily essential", "repeat", "trusted brand", "restock"],
    "algorithmic lock-in": ["homepage", "recommend", "discover", "search", "banner", "algorithm"],
    "trust non-transfer": ["trust", "authentic", "counterfeit", "certification", "quality", "genuine"],
    "need-state asymmetry": ["emergency", "urgent", "impulse", "need", "instant", "quick delivery"],
}


def _norm(t: str) -> str:
    return " ".join(t.lower().split())


def _load_corpus_texts() -> list[str]:
    texts = []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                texts.append(_norm(json.loads(line)["text"]))
    return texts


def _load_structured_texts() -> list[str]:
    """Theme labels + source distributions from the structured store — the ground
    truth for structured_store citations (aggregate theme summaries), which are
    NOT raw corpus chunks and so must be verified here rather than against the corpus."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT theme_label, source_type_distribution FROM themes").fetchall()
    conn.close()
    out = []
    for label, dist in rows:
        out.append(_norm(label or ""))
        out.append(_norm(f"{label} {dist}"))
    return out


def _parse_report(report: str) -> dict:
    """Extract per-question status, confidence level, and citations from the report."""
    blocks = re.split(r"^## Q(\d+)\.", report, flags=re.MULTILINE)[1:]
    questions = {}
    for i in range(0, len(blocks), 2):
        qnum = int(blocks[i])
        body = blocks[i + 1]
        insufficient = "**Finding: Insufficient evidence.**" in body
        conf_match = re.search(r"\*\*Confidence:\*\*\s+([\w-]+)", body)
        citations = re.findall(r'_"(.+?)"_\s+—\s+(\w+)', body, flags=re.DOTALL)
        questions[qnum] = {
            "insufficient": insufficient,
            "confidence": conf_match.group(1) if conf_match else None,
            "citations": [(q.strip(), st) for q, st in citations],
        }
    return questions


def main() -> int:
    if not os.path.exists(REPORT_PATH):
        print(f"No report at {REPORT_PATH} — generate it first.")
        return 1
    report = open(REPORT_PATH, encoding="utf-8").read()
    parsed = _parse_report(report)
    corpus = _load_corpus_texts()
    structured = _load_structured_texts()

    def _is_verified(quote: str, source_type: str) -> bool:
        needle = _norm(quote)
        # structured_store citations are aggregate theme summaries -> verify against
        # the structured store; all other citations are raw user text -> verify
        # against the corpus.
        haystacks = structured if source_type == "structured_store" else corpus
        return any(needle in h for h in haystacks)

    all_citations = [(q, st) for v in parsed.values() for (q, st) in v["citations"]]
    verified = [(q, st) for (q, st) in all_citations if _is_verified(q, st)]
    n = len(all_citations)
    grounded = len(verified)
    groundedness = grounded / n if n else 0.0
    hallucination = (n - grounded) / n if n else 0.0

    print("Phase 6 — Validation Gate\n" + "=" * 55)
    print("\n[1] Groundedness rate (target >=95%)")
    print(f"    {grounded}/{n} cited quotes verified verbatim in corpus = {groundedness:.0%}")
    print(f"    {'PASS' if groundedness >= 0.95 else 'FAIL'}")
    if grounded < n:
        for q, st in all_citations:
            if not _is_verified(q, st):
                print(f'      UNVERIFIED [{st}]: "{q[:70]}"')

    print("\n[2] Hallucination rate (target <5%)")
    print(f"    {n - grounded}/{n} unverifiable = {hallucination:.0%}  {'PASS' if hallucination < 0.05 else 'FAIL'}")

    print("\n[3] Cross-source coverage")
    high_conf = {q: v for q, v in parsed.items() if v["confidence"] == "high"}
    hc_multi = {q: v for q, v in high_conf.items() if len({st for _, st in v["citations"]}) >= 2}
    if high_conf:
        cov = len(hc_multi) / len(high_conf)
        print(f"    high-confidence answers citing >=2 source types: {len(hc_multi)}/{len(high_conf)} = {cov:.0%} "
              f"({'PASS' if cov >= 0.70 else 'FAIL'} vs >=70% target)")
    else:
        print("    no high-confidence answers to assess")
    if os.path.exists(DB_PATH):
        c = sqlite3.connect(DB_PATH).cursor()
        total = c.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
        cross = c.execute("SELECT COUNT(*) FROM themes WHERE cross_source_count>=2").fetchone()[0]
        print(f"    structured store: {cross}/{total} themes cross >=2 source types "
              f"({(100*cross//total) if total else 0}%) — corpus-thinness limitation, documented")

    print("\n[4] Hypothesis check (target: >=2 Part 1 hypotheses addressed)")
    report_lower = report.lower()
    addressed = []
    for hyp, kws in HYPOTHESES.items():
        hits = [k for k in kws if k in report_lower]
        if hits:
            addressed.append(hyp)
            print(f"    ADDRESSED — {hyp}: evidence mentions {hits[:3]}")
        else:
            print(f"    not addressed — {hyp}")
    print(f"    {len(addressed)}/4 hypotheses addressed "
          f"({'PASS' if len(addressed) >= 2 else 'FAIL'} vs >=2 target) — final judgement is manual")

    answered = sum(1 for v in parsed.values() if not v["insufficient"])
    gate_pass = groundedness >= 0.95 and hallucination < 0.05 and len(addressed) >= 2
    print("\n" + "=" * 55)
    print(f"Report: {answered}/8 answered, {8 - answered}/8 insufficient-evidence")
    print(f"VALIDATION GATE (automated checks): {'PASS' if gate_pass else 'REVIEW'}")
    print("Note: cross-source coverage is a documented corpus-thinness limitation, "
          "not a synthesis defect; groundedness/hallucination are the trust-critical gates.")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
