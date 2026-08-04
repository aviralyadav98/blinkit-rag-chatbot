"""
Phase 9 — Web frontend (docs/IMPLEMENTATION.md Phase 9).

A single Streamlit app that puts BOTH deliverables on the web, over the exact
same backend as the terminal tools — no new retrieval or synthesis:

  - "Chat" tab   -> wraps app/chatbot.py's ChatSession (Layer 2) in a chat UI.
  - "Report" tab -> renders the already-generated docs/INSIGHT_REPORT.md (Layer 1).

Deliberately, the Report tab DISPLAYS the report file; it does not regenerate it
per visitor. Regeneration stays on the Phase 8 refresh schedule (report_agent.py
+ validate.py), so no visitor page-load ever burns Groq quota or ships an
unvalidated report. The web layer is a read-only window onto whatever the last
validated refresh produced.

Run locally:
    .venv/Scripts/python.exe -m streamlit run app/web_app.py

Deploy (free): Hugging Face Spaces, Streamlit SDK. GROQ_API_KEY goes in the
Space's Secrets (never committed), same discipline as the local .env. The model
(bge-m3, ~2.3GB) loads once per container via @st.cache_resource, not per turn.
"""

import os
import sys
import time

import streamlit as st

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_APP_DIR, ".."))
# Same import wiring the terminal entry points use, so the web app calls the
# identical retriever + synthesis modules rather than a forked copy.
sys.path.insert(0, _APP_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "rag"))

# Load .env before importing the backend so the Cloudflare-embedding creds are in
# os.environ regardless of import order (locally). On Streamlit Cloud the secrets
# are already in the environment, so this is a no-op there.
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

# On Streamlit Community Cloud, secrets are provided via st.secrets (not os.environ),
# but the backend reads os.getenv(...). Bridge them so GROQ/Cloudflare creds are found.
# Locally these come from .env, so this is a harmless no-op there.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

# Point Chroma at a fresh, writable ephemeral dir and rebuild it from the portable
# JSONL at startup (see get_session). The committed rag/chroma_data index is written
# by a specific chromadb version; the host may run a different one that can't read it
# (chromadb.errors.NotFoundError). Rebuilding from JSONL sidesteps that entirely.
import tempfile  # noqa: E402

os.environ["CHROMA_PERSIST_DIR"] = os.path.join(tempfile.gettempdir(), "blinkit_chroma")

from chatbot import ChatSession  # noqa: E402
from load_chroma import build_collection  # noqa: E402

REPORT_PATH = os.path.join(_PROJECT_ROOT, "docs", "INSIGHT_REPORT.md")

# Source types a visitor can filter the chat on — mirror the metadata values the
# corpus actually carries (rag/retriever.py `source_type`).
SOURCE_TYPES = [
    "app_store_review",
    "play_store_review",
    "reddit",
    "comparison_content",
]

st.set_page_config(page_title="Blinkit review analyser", page_icon="🛒", layout="centered")


@st.cache_resource(show_spinner="Building the search index from the corpus (first load only)…")
def get_session() -> ChatSession:
    """One ChatSession per container. Runs once (cached): rebuilds the Chroma index
    from the portable JSONL into the ephemeral dir, then returns a session. Query
    embedding goes through Cloudflare (no local model), so this is fast."""
    build_collection()
    return ChatSession()


@st.cache_data
def load_report() -> str | None:
    if not os.path.exists(REPORT_PATH):
        return None
    with open(REPORT_PATH, encoding="utf-8") as f:
        return f.read()


def _render_result(result: dict) -> None:
    """Render a synthesis result with the same grounding surface as the terminal
    tools: explicit insufficient-evidence, confidence signal, and per-claim
    citations (quote + source type + date + click-through link)."""
    if result["status"] == "insufficient_evidence":
        st.warning(f"**Insufficient evidence.** {result['answer']}")
        st.caption(
            "This is a reported finding, not an error — the corpus did not contain "
            "enough grounded signal to answer without guessing."
        )
        return

    st.markdown(result["answer"])
    conf = result["confidence"]
    st.caption(f"Confidence: **{conf['level']}** — {conf['summary']}")

    with st.expander(f"Evidence ({len(result['claims'])} claims, cited)"):
        for claim in result["claims"]:
            st.markdown(f"- {claim['statement']}")
            for cite in claim["citations"]:
                src = cite.get("source_url") or ""
                link = f" — [source]({src})" if src.startswith("http") else ""
                st.markdown(
                    f'    > _"{cite["quote"]}"_ — {cite["source_type"]}, '
                    f'{cite["approx_date"]}{link}'
                )


def chat_tab() -> None:
    st.subheader("Ask about category cross-sell behavior")
    st.caption(
        "Grounded only in real public user language. Every answer cites its sources; "
        "when evidence is thin, it says so instead of guessing. Hinglish is fine."
    )

    with st.sidebar:
        st.header("Filters")
        picked = st.multiselect("Restrict to source types", SOURCE_TYPES, default=[])
        since = st.text_input("Only passages on/after (YYYY-MM-DD)", value="")
        if st.button("Clear conversation"):
            st.session_state.pop("messages", None)
            get_session().history = []
            st.rerun()

    session = get_session()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                _render_result(m["content"])

    prompt = st.chat_input("e.g. What frustrations come up most often?")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Retrieving + synthesizing…"):
                t0 = time.time()
                result = session.ask(
                    prompt,
                    source_types=picked or None,
                    since_date=since.strip() or None,
                )
                dt = time.time() - t0
            _render_result(result)
            st.caption(f"{dt:.1f}s")
        st.session_state.messages.append({"role": "assistant", "content": result})


def report_tab() -> None:
    report = load_report()
    if report is None:
        st.info(
            "No report found yet. Generate it with `app/report_agent.py` (or the "
            "`refresh.py` pipeline); this tab displays whatever the last validated "
            "run produced."
        )
        return
    st.download_button("Download report (Markdown)", report, file_name="INSIGHT_REPORT.md")
    st.markdown(report)


def main() -> None:
    st.title("🛒 Blinkit review analyser")
    if not os.getenv("GROQ_API_KEY"):
        st.error(
            "GROQ_API_KEY is not set. Locally: put it in `.env`. On Hugging Face "
            "Spaces: add it under Settings → Secrets. The chat tab can't synthesize "
            "answers without it."
        )
    tab_chat, tab_report = st.tabs(["Chat (Layer 2)", "Insight Report (Layer 1)"])
    with tab_chat:
        chat_tab()
    with tab_report:
        report_tab()


if __name__ == "__main__":
    main()
else:
    # `streamlit run` imports the module rather than calling it as __main__.
    main()
