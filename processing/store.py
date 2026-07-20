"""
Phase 2 step 6 — Structured store (docs/ARCHITECTURE.md Sec. 4 Data Model).

SQLite, separate from the vector store: theme x frequency x source x severity
x habit/frustration/discovery/propensity, used for the confidence/frequency
signal and audit trail. `source_type_distribution` is kept as a JSON blob
(exact counts per source type) plus a derived `cross_source_count` column so
the "≥2 source types = high confidence" rule (CLAUDE.md non-negotiable) can be
checked with a plain SQL WHERE clause, not JSON parsing.
"""

import json
import os
import sqlite3

MAX_QUOTES_PER_THEME = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS themes (
    theme_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id INTEGER NOT NULL,
    theme_label TEXT NOT NULL,
    sentiment TEXT,
    habit_type TEXT,
    frustration_type TEXT,
    discovery_path TEXT,
    experimentation_propensity TEXT,
    frequency_count INTEGER NOT NULL,
    source_type_distribution TEXT NOT NULL,  -- JSON: {"reddit": 12, "forum": 2, ...}
    cross_source_count INTEGER NOT NULL,     -- number of distinct source_types
    first_seen_date TEXT,
    last_seen_date TEXT
);

CREATE TABLE IF NOT EXISTS quotes (
    quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL REFERENCES themes(theme_id),
    chunk_id TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    approx_date TEXT,
    quote_text TEXT NOT NULL
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    # Reset both tables so the structured store reflects the CURRENT corpus, not
    # an accumulation across every past processing run. write_theme only INSERTs,
    # and cluster_ids are reassigned each run, so without this a re-run would pile
    # stale themes on top of the fresh ones (corrupting Phase 4 confidence lookups
    # and the Phase 5 report). A processing run always rebuilds this store from
    # scratch — the audit trail lives in the raw corpus + chunks, not here.
    conn.execute("DELETE FROM quotes")
    conn.execute("DELETE FROM themes")
    conn.commit()
    return conn


def write_theme(conn: sqlite3.Connection, label: dict, cluster_chunks: list[dict]) -> int:
    """Writes one cluster's label + its quotes. Returns the new theme_id."""
    source_dist: dict[str, int] = {}
    dates = []
    for c in cluster_chunks:
        source_dist[c["source_type"]] = source_dist.get(c["source_type"], 0) + 1
        if c.get("approx_content_date"):
            dates.append(str(c["approx_content_date"]))
    dates.sort()

    cur = conn.execute(
        """INSERT INTO themes
           (cluster_id, theme_label, sentiment, habit_type, frustration_type,
            discovery_path, experimentation_propensity, frequency_count,
            source_type_distribution, cross_source_count, first_seen_date, last_seen_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            label.get("cluster_id"),
            label.get("theme", "untitled"),
            label.get("sentiment"),
            label.get("habit_type"),
            label.get("frustration_type"),
            label.get("discovery_path"),
            label.get("experimentation_propensity"),
            len(cluster_chunks),
            json.dumps(source_dist),
            len(source_dist),
            dates[0] if dates else None,
            dates[-1] if dates else None,
        ),
    )
    theme_id = cur.lastrowid

    # Persist a capped sample of chunks per theme as audit quotes (every theme
    # must have click-through-able sources — CLAUDE.md non-negotiable). Prefer
    # chunks whose text overlaps the LLM's chosen example snippets (substring
    # match, since the LLM shortens/reformats them), then fill with the rest so
    # no theme ends up with zero quotes.
    example_snippets = [q for q in (label.get("example_quotes") or []) if isinstance(q, str)]

    def _matches_example(chunk_text: str) -> bool:
        return any(snip[:40].lower() in chunk_text.lower() for snip in example_snippets if snip)

    preferred = [c for c in cluster_chunks if _matches_example(c["text"])]
    rest = [c for c in cluster_chunks if c not in preferred]
    quotes_to_store = (preferred + rest)[:MAX_QUOTES_PER_THEME]

    for c in quotes_to_store:
        conn.execute(
            """INSERT INTO quotes (theme_id, chunk_id, source_type, source_url, approx_date, quote_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                theme_id,
                c.get("chunk_id"),
                c["source_type"],
                c["source_url"],
                c.get("approx_content_date"),
                c["text"][:1000],
            ),
        )
    conn.commit()
    return theme_id
