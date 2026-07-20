"""
Phase 4 exit-criteria check (docs/IMPLEMENTATION.md Phase 4).

Given a known-answerable question (Q6 frustrations — dense App Store data) and a
known-unanswerable one (Q7 user segments — genuine corpus sparsity), the engine
must produce a cited answer for the first and an explicit insufficient-evidence
response for the second.

    .venv/Scripts/python.exe app/test_synthesis.py
"""

import os
import sys

# Wire in the retriever (rag/) alongside this app module.
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))

from retriever import Retriever  # noqa: E402

from synthesis import synthesize  # noqa: E402

ANSWERABLE = ("What frustrations do Blinkit users mention repeatedly?",
              ["app_store_review", "play_store_review", "reddit"])
UNANSWERABLE = ("Which types of users are more likely to try new categories?", None)


def _run(question: str, source_types, retriever) -> dict:
    passages = retriever.retrieve(question, k=5, source_types=source_types)
    return synthesize(question, passages)


def _print(label: str, result: dict) -> None:
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    print(f"Q: {result['question']}")
    print(f"status: {result['status']}")
    print(f"confidence: {result['confidence']['level']} — {result['confidence']['summary']}")
    print(f"answer: {result['answer']}")
    if result["claims"]:
        print("claims:")
        for c in result["claims"]:
            print(f"  • {c['statement']}")
            for cite in c["citations"]:
                print(f"      [{cite['source_type']} | {cite['approx_date']}] \"{cite['quote'][:80]}\"")
    if result["citations_dropped"]:
        print(f"(citations dropped in verification: {result['citations_dropped']})")


def main() -> int:
    r = Retriever()
    ans = _run(*ANSWERABLE, r)
    _print("KNOWN-ANSWERABLE (Q6 frustrations)", ans)
    una = _run(*UNANSWERABLE, r)
    _print("KNOWN-UNANSWERABLE (Q7 segments)", una)

    ok = ans["status"] == "answered" and len(ans["claims"]) > 0 and una["status"] == "insufficient_evidence"
    print(f"\n{'=' * 60}")
    print(f"EXIT CRITERIA: {'PASS' if ok else 'FAIL'}")
    print(f"  answerable -> cited answer: {ans['status'] == 'answered' and len(ans['claims']) > 0}")
    print(f"  unanswerable -> insufficient evidence: {una['status'] == 'insufficient_evidence'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
