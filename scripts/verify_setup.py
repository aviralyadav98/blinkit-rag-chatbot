"""
Phase 0 exit-criteria check (docs/IMPLEMENTATION.md):
"a script can call the Groq API, an Apify actor, and write/read a local Chroma
collection, each in isolation."

Each check is independent — one failing (e.g. a missing key) does not stop the
others from running. Run after populating .env:

    .venv/Scripts/python.exe scripts/verify_setup.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def check_groq() -> tuple[bool, str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return False, "GROQ_API_KEY not set in .env"
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK."}],
        )
        text = resp.choices[0].message.content.strip() if resp.choices else ""
        return True, f"Groq API reachable — reply: {text!r}"
    except Exception as e:
        return False, f"Groq API call failed: {e}"


def check_apify() -> tuple[bool, str]:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        return False, "APIFY_TOKEN not set in .env"
    try:
        from apify_client import ApifyClient

        client = ApifyClient(token)
        # Metadata fetch only (no run, no cost) — confirms the token can reach
        # one of the Phase 1 actors before any paid scrape is triggered.
        actor = client.actor("neatrat/google-play-store-reviews-scraper").get()
        if actor is None:
            return False, "Actor lookup returned nothing — check token/actor access"
        return True, f"Apify reachable — actor '{actor.name}' accessible"
    except Exception as e:
        return False, f"Apify API call failed: {e}"


def check_chroma() -> tuple[bool, str]:
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./rag/chroma_data")
    try:
        import chromadb

        client = chromadb.PersistentClient(path=persist_dir)
        # Pass an explicit embedding rather than relying on Chroma's default
        # embedding function (which lazily downloads an ONNX model) — the real
        # pipeline embeds via BAAI/bge-m3 before anything reaches Chroma, so this
        # check should only prove Chroma itself can write/read, not fetch a model.
        collection = client.get_or_create_collection(
            "phase0_setup_check", metadata={"hnsw:space": "cosine"}
        )
        dummy_embedding = [0.1] * 8
        collection.upsert(
            ids=["smoke-1"],
            embeddings=[dummy_embedding],
            documents=["Blinkit users repeatedly buy from the same categories."],
            metadatas=[{"source_type": "smoke_test"}],
        )
        result = collection.query(query_embeddings=[dummy_embedding], n_results=1)
        client.delete_collection("phase0_setup_check")
        got = result["documents"][0][0] if result["documents"][0] else None
        return True, f"Chroma write/read OK at '{persist_dir}' — retrieved: {got!r}"
    except Exception as e:
        return False, f"Chroma write/read failed: {e}"


def main() -> int:
    checks = [
        ("Groq API", check_groq),
        ("Apify actor", check_apify),
        ("Chroma read/write", check_chroma),
    ]

    results = []
    for name, fn in checks:
        try:
            ok, message = fn()
        except Exception as e:  # belt-and-suspenders — one check must never abort the rest
            ok, message = False, f"unexpected error: {e}"
        results.append((name, ok, message))

    print("\nPhase 0 setup verification\n" + "-" * 40)
    for name, ok, message in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {message}")

    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
