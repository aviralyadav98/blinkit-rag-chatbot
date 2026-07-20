"""
Phase 4/5 — structured-store context for synthesis (completes the design in
docs/ARCHITECTURE.md Sec. 3.4 / IMPLEMENTATION.md Phase 4: "answers can pull the
richer habit_type / frustration_type / discovery_path / experimentation_propensity
distributions directly from the structured store").

The aggregate "how often does X recur across many users" signal lives in the
structured store's per-theme frequency counts — pure passage retrieval can't see
it, so questions phrased as "emerges repeatedly / consistently" can't be grounded
from passages alone. This module turns the store into a short evidence summary
that is fed to synthesis as one additional passage (source_type "structured_store").

It does NOT replace citations: the summary grounds the frequency/quantifier part
of an answer, and synthesis still cites specific passages for the substance. Theme
LABELS are included so the model can judge on-topic-ness itself (some tags landed
on tangential themes due to labeling noise — showing the label lets the model
discount "SRM University admission [information]" while trusting "Poor customer
service and delivery issues [delivery], 24 reviews").
"""

import os
import sqlite3

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.getenv("SQLITE_DB_PATH", "processing/insights.db")
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(_PROJECT_ROOT, DB_PATH)

# Which structured-store tag column best supplies the aggregate signal for each
# of the 8 fixed questions (by 1-based index).
QUESTION_DIMENSION = {
    1: "habit_type",                  # repeat buying
    2: "frustration_type",            # barriers
    3: "discovery_path",              # discovery
    4: "habit_type",                  # habits
    5: "frustration_type",            # info needs
    6: "frustration_type",            # frustrations
    7: "experimentation_propensity",  # segments
    8: "frustration_type",            # unmet needs
}

_ALLOWED_DIMENSIONS = {"habit_type", "frustration_type", "discovery_path", "experimentation_propensity"}
_NULLISH = ("null", "none", "", "n/a", "na")
MAX_THEMES = 8


def build_structured_context(dimension: str) -> str | None:
    """A short evidence summary of the top themes carrying a value for `dimension`,
    ordered by frequency, with each theme's label, tag value, chunk count, and
    source-type spread. Returns None if the dimension is unknown or the store has
    nothing for it."""
    if dimension not in _ALLOWED_DIMENSIONS or not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            f"""SELECT theme_label, {dimension}, frequency_count, source_type_distribution
                FROM themes
                WHERE {dimension} IS NOT NULL AND LOWER({dimension}) NOT IN ({','.join('?' * len(_NULLISH))})
                ORDER BY frequency_count DESC
                LIMIT ?""",
            (*_NULLISH, MAX_THEMES),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return None

    if not rows:
        return None

    lines = [
        f"Structured-store aggregate signal for '{dimension}' (theme frequencies across the "
        f"whole corpus — use these counts to judge how often something recurs; still cite "
        f"specific passages below for the substance):"
    ]
    for label, tag, freq, dist in rows:
        lines.append(f'- "{label}" [{tag}] — {freq} chunks; sources: {dist}')
    return "\n".join(lines)


def context_for_question(index: int) -> str | None:
    dimension = QUESTION_DIMENSION.get(index)
    return build_structured_context(dimension) if dimension else None
