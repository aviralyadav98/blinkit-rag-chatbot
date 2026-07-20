"""
Consistency gate for the Cloudflare bge-m3 query-embedding path (Phase 9 rehost).

Before we trust Cloudflare Workers AI's `@cf/baai/bge-m3` as a drop-in for the
local model, this checks that its query embeddings agree with the LOCAL bge-m3
the corpus was built with. If they don't, retrieval would silently degrade.

    .venv/Scripts/python.exe rag/test_cloudflare_embed.py

Requires CF_ACCOUNT_ID + CF_API_TOKEN in .env, and the local model available.
For each probe it prints cosine(local, cloudflare):
  >= 0.98  -> drop-in safe; keep the existing corpus, only queries go via CF.
  < 0.98   -> re-embed the corpus THROUGH Cloudflare too, so both sides match.
"""

import math
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

import vector_store as vs  # noqa: E402

PROBES = [
    "Why do users repeatedly buy from the same categories?",
    "What frustrations emerge repeatedly?",
    "Blinkit pe skincare order karna theek hai kya, ya risky hai?",  # Hinglish
    "quick commerce baby products delivery",
]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def main() -> int:
    if not vs._using_cloudflare():
        print("CF_ACCOUNT_ID / CF_API_TOKEN not set in .env — cannot test. Add them first.")
        return 2

    local_model = vs._get_model()
    worst = 1.0
    print(f"{'cosine':>8}  probe")
    for p in PROBES:
        local_vec = local_model.encode([p], normalize_embeddings=True)[0].tolist()
        cf_vec = vs._embed_query_cloudflare(p)
        if len(local_vec) != len(cf_vec):
            print(f"DIMENSION MISMATCH: local={len(local_vec)} cloudflare={len(cf_vec)} — not a drop-in.")
            return 1
        c = _cosine(local_vec, cf_vec)
        worst = min(worst, c)
        print(f"{c:8.4f}  {p[:60]}")

    print(f"\nworst cosine: {worst:.4f}")
    if worst >= 0.98:
        print("PASS — Cloudflare bge-m3 matches local. Keep the corpus; route only queries via CF.")
        return 0
    print("BELOW THRESHOLD — re-embed the corpus through Cloudflare so both sides use the same endpoint.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
