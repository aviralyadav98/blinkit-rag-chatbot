"""
Phase 2 step 5 — Label clusters (docs/IMPLEMENTATION.md Phase 2, CLAUDE.md decided
architecture).

Groq (`llama-3.3-70b-versatile`) reads cluster-representative chunks only —
never the full raw corpus — and emits structured JSON: theme, sentiment, plus
the richer PM-facing tags (habit_type, frustration_type, discovery_path,
experimentation_propensity). This is the only LLM pass over raw text at
ingestion/processing time.

Enums are fixed for now (docs/ARCHITECTURE.md Sec. 6 open question — revisit
if early clusters don't fit cleanly): the model is instructed to use "other"
or null rather than inventing a new category, and to ground every field only
in the passages it's given.
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# llama-3.1-8b-instant chosen over 70b for labeling: Groq's free tier caps the
# 70b model at 100k tokens/day, which one full labeling run exhausts. The 8b
# model has a much higher free daily allowance, so re-runs don't block. Cluster
# labeling (theme name + sentiment + fixed-enum tags) is well within 8b's
# ability; outputs are spot-checked regardless (CLAUDE.md working convention).
MODEL = "llama-3.1-8b-instant"
# Keep per-cluster token usage modest even so — 5 chunks x 500 chars.
MAX_REPRESENTATIVE_CHUNKS = 5
CHUNK_CHARS_IN_PROMPT = 500

SYSTEM_PROMPT = """You are labeling a cluster of user-generated passages (reviews, \
Reddit posts, forum posts) about Blinkit, a quick-commerce grocery app, for a \
research report on why users don't explore new product categories.

You will be given several passages that a clustering algorithm grouped together \
because they are semantically similar. Read ONLY the passages given — do not use \
outside knowledge about Blinkit, and do not assert anything the passages don't \
support.

Respond with ONLY a JSON object (no other text), with exactly these fields:
{
  "theme": "<a short (5-10 word) label for what this cluster is actually about>",
  "sentiment": "<one of: positive, negative, neutral, mixed>",
  "habit_type": "<one of: repetitive, exploratory, null - null if the passages don't speak to purchase habits>",
  "frustration_type": "<one of: delivery, pricing, discovery, information, trust, other, null - null if no frustration is expressed>",
  "discovery_path": "<one of: search, homepage_banner, offers, external_recommendation, other, null - null if not discussed>",
  "experimentation_propensity": "<one of: high, medium, low, null - null if not inferable>",
  "example_quotes": ["<verbatim short quote from the passages, up to 3>"]
}"""


def _build_user_prompt(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks):
        lines.append(f"[Passage {i + 1} | source: {c['source_type']}]\n{c['text'][:CHUNK_CHARS_IN_PROMPT]}")
    return "\n\n".join(lines)


def _select_representative_chunks(cluster_chunks: list[dict]) -> list[dict]:
    if len(cluster_chunks) <= MAX_REPRESENTATIVE_CHUNKS:
        return cluster_chunks
    # even spread across the cluster rather than just the first N
    step = len(cluster_chunks) / MAX_REPRESENTATIVE_CHUNKS
    return [cluster_chunks[int(i * step)] for i in range(MAX_REPRESENTATIVE_CHUNKS)]


def _parse_json_response(content: str) -> dict:
    """Parse the model's JSON, tolerant of the malformed output the 8b model
    occasionally produces (raw control characters, stray text around the object,
    trailing commas). JSON mode on the API side prevents most of this; this is
    the belt-and-suspenders fallback."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # isolate the outermost JSON object
    start, end = content.find("{"), content.rfind("}")
    candidate = content[start : end + 1] if start != -1 and end != -1 else content

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # escape raw control chars (unescaped newlines/tabs inside strings) and
    # strip trailing commas before a closing brace/bracket
    repaired = re.sub(r"[\x00-\x1f]", lambda m: {"\n": "\\n", "\t": "\\t", "\r": "\\r"}.get(m.group(), " "), candidate)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return json.loads(repaired)  # if this still raises, the caller records the failure


def label_cluster(cluster_chunks: list[dict], client: Groq, retries: int = 1) -> dict:
    representative = _select_representative_chunks(cluster_chunks)
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(representative)},
            ],
            temperature=0.2,
            max_tokens=500,
            # JSON mode: forces syntactically valid JSON, the main fix for the
            # occasional malformed-output failures seen with this model.
            response_format={"type": "json_object"},
        )
        try:
            label = _parse_json_response(resp.choices[0].message.content)
            label["cluster_id"] = cluster_chunks[0]["cluster_id"]
            return label
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e  # transient malformed output — retry once before giving up
    raise last_err


def label_all_clusters(chunks: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Groups chunks by cluster_id (skipping noise, -1) and labels each cluster.

    Returns a list of (label_dict, cluster_chunks) pairs.
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    by_cluster: dict[int, list[dict]] = {}
    for c in chunks:
        if c["cluster_id"] == -1:
            continue
        by_cluster.setdefault(c["cluster_id"], []).append(c)

    results = []
    for cluster_id, cluster_chunks in sorted(by_cluster.items()):
        try:
            label = label_cluster(cluster_chunks, client)
            results.append((label, cluster_chunks))
        except Exception as e:
            print(f"[cluster {cluster_id}] labeling FAILED, skipping: {e}")
    return results
