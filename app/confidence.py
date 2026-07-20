"""
Phase 4 — confidence signal (docs/IMPLEMENTATION.md Phase 4, CLAUDE.md non-negotiables).

The confidence signal is computed here, NOT invented by the LLM: it is derived
from (a) the source-type spread of the retrieved passages actually supporting an
answer, and (b) the Phase 2 structured store's per-theme frequency counts,
looked up via each passage's cluster_id.

The rule (CLAUDE.md non-negotiable): a claim is "high confidence" only when it is
supported across >= 2 distinct source types. Single-source support is labeled as
such, explicitly, and never silently upgraded. Exposure is qualitative + counts
(the decided output format), e.g. "seen across 12 app-store reviews and 1 Reddit
thread (2 source types)" vs. "single-source, mentioned once".
"""

import os
import sqlite3

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.getenv("SQLITE_DB_PATH", "processing/insights.db")
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(_PROJECT_ROOT, DB_PATH)

# Human-readable source-type labels for the confidence summary.
SOURCE_LABELS = {
    "app_store_review": "App Store reviews",
    "play_store_review": "Play Store reviews",
    "reddit": "Reddit posts/comments",
    "forum": "forum posts",
    "comparison_content": "comparison/editorial articles",
}


def _theme_frequency_for_clusters(cluster_ids: list[int]) -> int:
    """Sum of frequency_count for the themes matching these clusters (structured
    store), i.e. how many chunks those themes were built from. 0 if the DB or
    rows are missing — confidence then rests on the passage spread alone."""
    real_ids = [c for c in cluster_ids if isinstance(c, int) and c >= 0]
    if not real_ids or not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        placeholders = ",".join("?" for _ in real_ids)
        row = conn.execute(
            f"SELECT COALESCE(SUM(frequency_count), 0) FROM themes WHERE cluster_id IN ({placeholders})",
            real_ids,
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def compute_confidence(passages: list[dict]) -> dict:
    """Build the confidence signal from the passages supporting an answer.

    `passages` are retriever hits: {text, metadata{source_type, cluster_id, ...}, distance}.
    Returns {level, summary, n_passages, source_types, theme_frequency}.
    """
    if not passages:
        return {
            "level": "insufficient",
            "summary": "no supporting passages retrieved",
            "n_passages": 0,
            "source_types": [],
            "theme_frequency": 0,
        }

    source_counts: dict[str, int] = {}
    cluster_ids = []
    for p in passages:
        st = p["metadata"].get("source_type", "unknown")
        source_counts[st] = source_counts.get(st, 0) + 1
        cluster_ids.append(p["metadata"].get("cluster_id"))

    n_source_types = len(source_counts)
    theme_freq = _theme_frequency_for_clusters(cluster_ids)

    # Non-negotiable (CLAUDE.md): "high confidence" ONLY when >= 2 source types
    # agree. Everything else is single-source and must be labeled as such — a
    # large count of same-source passages is still single-source, never upgraded.
    level = "high" if n_source_types >= 2 else "single-source"

    parts = []
    for st, cnt in sorted(source_counts.items(), key=lambda kv: -kv[1]):
        label = SOURCE_LABELS.get(st, st)
        parts.append(f"{cnt} {label}")
    if level == "high":
        summary = f"seen across {', '.join(parts)} ({n_source_types} source types)"
    else:
        summary = f"single-source: {', '.join(parts)}"

    return {
        "level": level,
        "summary": summary,
        "n_passages": len(passages),
        "source_types": sorted(source_counts.keys()),
        "theme_frequency": theme_freq,
    }
