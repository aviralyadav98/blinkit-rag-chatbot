"""
Phase 3 — retriever (docs/IMPLEMENTATION.md Phase 3, docs/ARCHITECTURE.md Sec. 3.3).

The single retrieval interface both Layer 1's fixed questions and Layer 2's chat
filters call. Semantic search over Chroma, with optional metadata pre-filters
(source type / category / recency) applied as a Chroma `where` clause before
the vector search, so filtering never depends on a second index.

Recency filter note: chunks store `approx_content_date` as an ISO string, so a
lexicographic ">=" comparison on YYYY-MM-DD... is a correct date comparison.
Chroma's `where` doesn't do string range ops, so recency is applied as a
post-filter on returned hits rather than in the `where` clause.
"""

from vector_store import get_client, get_collection, query


class Retriever:
    def __init__(self):
        self._collection = get_collection(get_client())

    def retrieve(
        self,
        question: str,
        k: int = 5,
        source_types: list[str] | None = None,
        category: str | None = None,
        since_date: str | None = None,
    ) -> list[dict]:
        where = self._build_where(source_types, category)
        # Over-fetch when a recency post-filter is in play, so we still return ~k
        # after dropping older hits.
        fetch_k = k * 4 if since_date else k
        hits = query(self._collection, question, k=fetch_k, where=where)

        if since_date:
            hits = [h for h in hits if (h["metadata"].get("approx_content_date") or "") >= since_date]

        return hits[:k]

    @staticmethod
    def _build_where(source_types: list[str] | None, category: str | None) -> dict | None:
        clauses = []
        if source_types:
            clauses.append({"source_type": {"$in": source_types}})
        if category:
            clauses.append({"category_hint": category})
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}
