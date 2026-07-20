"""
Phase 2 step 1 — Clean (docs/IMPLEMENTATION.md Phase 2, docs/ARCHITECTURE.md Sec. 3.2).

- Deduplicate near-identical records (exact-match on normalized text; common
  with scraped reviews/reposts).
- Filter spam and extremely short / non-informative text before it reaches
  embedding.
- Language-tag each record (tagging only, no translation — Hinglish/
  code-switched text is preserved as-is per CLAUDE.md non-negotiable).
"""

import re

from langdetect import DetectorFactory, LangDetectException, detect
from scrubber import scrub_pii

DetectorFactory.seed = 0  # deterministic language detection

MIN_TEXT_LENGTH = 15  # chars; below this a review is just noise ("nice", "ok")

# Relevance filter for Reddit only. App/Play Store reviews are inherently about
# Blinkit (they're reviews of the Blinkit app), and forum/comparison content came
# from hand-picked category-relevant URLs — so those are kept as-is. Reddit, by
# contrast, was pulled partly from a broad r/india scrape that dragged in large
# amounts of off-topic content.
#
# A Reddit post must mention a quick-commerce BRAND or the quick-commerce FORMAT
# to survive. An earlier version also accepted bare category words (skincare,
# grocery, baby, delivery, ...), but those matched incidental mentions in wholly
# unrelated posts (roommate ads, a novel whose scene was a "delivery room",
# relationship threads) — ~24 such junk posts slipped through. Requiring a
# brand/format signal drops those cleanly; a category post that never references
# quick commerce is only tangential to this research anyway.
QC_BRAND_FORMAT_KEYWORDS = [
    # brands / players
    "blinkit", "grofers", "zepto", "instamart", "swiggy instamart", "swiggy grocery",
    "bigbasket", "bb now", "bbnow", "dunzo", "flipkart minutes", "jiomart",
    # quick-commerce format
    "quick commerce", "quick-commerce", "q-commerce", "qcommerce",
    "10 minute", "10-minute", "10 min delivery", "ten minute", "dark store",
    "instant delivery", "instant grocery", "grocery delivery", "quick delivery app",
]

SOURCE_TYPES_NEEDING_RELEVANCE = {"reddit"}


def is_relevant(doc: dict) -> bool:
    if doc.get("source_type") not in SOURCE_TYPES_NEEDING_RELEVANCE:
        return True
    text_lower = doc.get("text", "").lower()
    return any(kw in text_lower for kw in QC_BRAND_FORMAT_KEYWORDS)


def _normalize_for_dedup(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_spam_or_low_signal(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < MIN_TEXT_LENGTH:
        return True
    # a single repeated character/word run (e.g. "!!!!!!!!!!", "good good good good")
    words = stripped.split()
    if len(set(words)) == 1 and len(words) > 2:
        return True
    return False


def detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def clean_documents(docs: list[dict]) -> list[dict]:
    """Dedup + spam-filter + language-tag. Returns a new list; input is untouched."""
    seen_texts = set()
    cleaned = []
    for doc in docs:
        text = doc.get("text", "")
        if is_spam_or_low_signal(text):
            continue
        if not is_relevant(doc):
            continue
        norm = _normalize_for_dedup(text)
        if norm in seen_texts:
            continue
        seen_texts.add(norm)

        doc = dict(doc)
        doc["language"] = detect_language(text)
        # Scrub PII before this text flows to embedding / LLM / report / citations.
        # Language detection runs on the original text above (redaction tokens would
        # skew it); everything downstream uses the scrubbed text.
        doc["text"] = scrub_pii(text)
        cleaned.append(doc)
    return cleaned
