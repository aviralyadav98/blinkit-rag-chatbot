"""
Phase 2 — PII scrubbing (adopted from the Groww review-pulse architecture Sec. 7.1).

Runs inside the clean stage, BEFORE embedding, clustering, LLM labeling, synthesis,
and publishing — so no personal data reaches an embedding, a Groq prompt, the report,
or a citation. The scrubbed text becomes the canonical text everywhere downstream
(chunks, Chroma, quotes), so quote-validation compares against scrubbed text too and
never mismatches. Raw, unscrubbed text survives only in the gitignored raw cache
(ingestion/data/raw), for audit.

Deliberately KEEPS financial amounts (₹, rs, lakh, "10k") — those are useful theme
signal for a shopping-behavior corpus, not PII (same call the Groww design made).
"""

import re

# URLs: keep scheme+host+path, drop query/fragment (that's where tokens/ids live).
_URL_TOKEN_RE = re.compile(r"(https?://[^\s?#]+)[^\s]*")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Indian mobile: optional +91/91/0 prefix, then a 10-digit number starting 6–9,
# with an optional single separator. Digit-boundary lookarounds so it doesn't eat
# into a longer number (e.g. an Aadhaar run).
_PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+?91|0)[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)")
# PAN: 5 letters, 4 digits, 1 letter.
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# Aadhaar / other long numeric ids: 12+ consecutive digits.
_LONG_ID_RE = re.compile(r"(?<!\d)\d{12,}(?!\d)")


def scrub_pii(text: str) -> str:
    """Redact emails / phones / PAN / long id numbers / URL tokens. Idempotent."""
    if not text:
        return text
    text = _URL_TOKEN_RE.sub(r"\1", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _PAN_RE.sub("[ID]", text)
    text = _LONG_ID_RE.sub("[ID]", text)
    return text
