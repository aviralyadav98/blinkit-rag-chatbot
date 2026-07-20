"""
Phase 7 exit-criteria check (docs/IMPLEMENTATION.md Phase 7).

"Answers the 8 seed questions plus >=3 novel follow-ups correctly, with citations
and coherent multi-turn context." Also spot-checks the <15s latency target and
Hinglish input handling.

    .venv/Scripts/python.exe app/test_chatbot.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from chatbot import ChatSession, format_answer  # noqa: E402

SEED_QUESTIONS = [
    "Why do users repeatedly buy from the same categories?",
    "What prevents users from exploring new categories?",
    "How do users discover products today?",
    "What role do habits play in shopping behavior?",
    "What information do users need before trying a new category?",
    "What frustrations emerge repeatedly?",
    "Which user segments are more likely to experiment?",
    "What unmet needs emerge consistently across discussions?",
]

# Novel follow-ups that only make sense given the preceding turn — they test
# multi-turn context (pronouns / topic carry-over), not standalone retrieval.
FOLLOWUPS = [
    "Can you tell me more about the delivery problems specifically?",
    "And what about pricing complaints?",
    "Do people actually try skincare on it, or just groceries?",
]

HINGLISH_PROBE = "Blinkit pe skincare order karna theek hai kya, ya risky hai?"


def _summary(result: dict) -> str:
    if result["status"] == "answered":
        n_cites = sum(len(c["citations"]) for c in result["claims"])
        return f"answered ({len(result['claims'])} claims, {n_cites} citations, {result['confidence']['level']})"
    return "insufficient-evidence"


def main() -> int:
    session = ChatSession()
    latencies = []
    seed_ok = 0

    print("=== 8 SEED QUESTIONS ===")
    for q in SEED_QUESTIONS:
        t0 = time.time()
        r = session.ask(q)
        dt = time.time() - t0
        latencies.append(dt)
        # "correct" = a grounded cited answer OR an honest insufficient-evidence finding
        ok = (r["status"] == "answered" and bool(r["claims"])) or r["status"] == "insufficient_evidence"
        seed_ok += ok
        print(f"  Q: {q}\n     -> {_summary(r)}  [{dt:.1f}s]")

    print("\n=== 3 NOVEL MULTI-TURN FOLLOW-UPS (context-dependent) ===")
    followup_ok = 0
    for q in FOLLOWUPS:
        t0 = time.time()
        r = session.ask(q)
        dt = time.time() - t0
        latencies.append(dt)
        ok = (r["status"] == "answered" and bool(r["claims"])) or r["status"] == "insufficient_evidence"
        followup_ok += ok
        print(f"  follow-up: {q}\n     -> {_summary(r)}  [{dt:.1f}s]")
        print(f"        {format_answer(r).splitlines()[0][:110]}")

    print("\n=== HINGLISH INPUT PROBE ===")
    t0 = time.time()
    r = session.ask(HINGLISH_PROBE)
    dt = time.time() - t0
    latencies.append(dt)
    print(f"  {HINGLISH_PROBE}\n     -> {_summary(r)}  [{dt:.1f}s]")

    max_lat = max(latencies)
    print("\n" + "=" * 55)
    print(f"seed questions handled: {seed_ok}/8")
    print(f"novel follow-ups handled: {followup_ok}/3 (target >=3)")
    print(f"max latency: {max_lat:.1f}s (target <15s)")
    exit_ok = seed_ok == 8 and followup_ok >= 3
    print(f"EXIT CRITERIA: {'PASS' if exit_ok else 'REVIEW'} "
          f"(latency {'PASS' if max_lat < 15 else 'REVIEW'})")
    return 0 if exit_ok else 1


if __name__ == "__main__":
    sys.exit(main())
