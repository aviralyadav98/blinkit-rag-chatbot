"""
Phase 7 — Layer 2: RAG Chatbot (docs/IMPLEMENTATION.md Phase 7, STRETCH).

A thin conversational wrapper over the SAME backend as the report (the Phase 3
retriever + the Phase 4 synthesis engine) — it adds no new retrieval or synthesis,
just multi-turn state, query expansion, and filters on top. Every answer holds to
the same standard as the report: grounded only in retrieved passages, every claim
citation-verified, honest confidence, and explicit insufficient-evidence.

Differences from the report agent (both deliberate, prototype-appropriate):
  - Single synthesize() call per turn, not majority voting — the report votes for
    a stable regenerated artifact; the chatbot prioritizes the <15s interactive
    latency target. (Grounding safeguards are identical either way.)
  - Free-text questions, so no fixed per-question structured-store dimension; the
    structured signal is left off here.

Hinglish/code-switched input needs no special handling: bge-m3 embeds it natively
at the retrieval layer (no translation, per Non-Goals), same as the corpus.

Run interactively:
    .venv/Scripts/python.exe app/chatbot.py
Commands inside the REPL:
    /source app_store_review,reddit   restrict sources (blank to clear)
    /since 2026-01-01                 only passages on/after this date
    /reset                            clear conversation history
    /quit
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))

from retriever import Retriever  # noqa: E402

from synthesis import synthesize  # noqa: E402

RETRIEVE_K = 6


class ChatSession:
    """Multi-turn conversation over the shared retrieval+synthesis backend."""

    def __init__(self, retriever: Retriever | None = None):
        self.retriever = retriever or Retriever()
        self.history: list[dict] = []

    def _expand_query(self, question: str) -> str:
        """Fold the previous user turn into the retrieval query so follow-ups
        ("what about pricing?", "and for skincare?") resolve against the topic
        already under discussion. Only the retrieval query is expanded — the
        synthesis question stays the user's literal words, and full history is
        passed to synthesis separately for conversational coherence."""
        prev_user = [h["content"] for h in self.history if h["role"] == "user"]
        if not prev_user:
            return question
        return f"{prev_user[-1]} {question}".strip()

    def ask(
        self,
        question: str,
        source_types: list[str] | None = None,
        category: str | None = None,
        since_date: str | None = None,
    ) -> dict:
        retrieval_query = self._expand_query(question)
        passages = self.retriever.retrieve(
            retrieval_query,
            k=RETRIEVE_K,
            source_types=source_types,
            category=category,
            since_date=since_date,
        )
        result = synthesize(question, passages, history=self.history)
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": result["answer"]})
        return result


def format_answer(result: dict) -> str:
    lines = []
    if result["status"] == "insufficient_evidence":
        lines.append(f"[insufficient evidence] {result['answer']}")
        return "\n".join(lines)
    conf = result["confidence"]
    lines.append(result["answer"])
    lines.append(f"  confidence: {conf['level']} — {conf['summary']}")
    for claim in result["claims"]:
        lines.append(f"  • {claim['statement']}")
        for cite in claim["citations"]:
            src = cite.get("source_url") or cite["source_type"]
            lines.append(f'      \"{cite["quote"][:90]}\" — {cite["source_type"]}, {cite["approx_date"]} [{src}]')
    return "\n".join(lines)


def main() -> int:
    print("Blinkit RAG Chatbot (prototype). Type a question, or /quit. Filters: /source, /since, /reset.\n")
    session = ChatSession()
    source_types: list[str] | None = None
    since_date: str | None = None

    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/reset":
            session.history = []
            print("(history cleared)\n")
            continue
        if q.startswith("/source"):
            arg = q[len("/source"):].strip()
            source_types = [s.strip() for s in arg.split(",") if s.strip()] or None
            print(f"(sources = {source_types or 'all'})\n")
            continue
        if q.startswith("/since"):
            since_date = q[len("/since"):].strip() or None
            print(f"(since = {since_date or 'any'})\n")
            continue

        t0 = time.time()
        result = session.ask(q, source_types=source_types, since_date=since_date)
        dt = time.time() - t0
        print(f"\nbot> {format_answer(result)}\n  ({dt:.1f}s)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
