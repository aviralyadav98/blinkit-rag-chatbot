# Blinkit Category Cross-Sell — RAG Insights Chatbot

A RAG chatbot that answers behavioral research questions about Blinkit's category
cross-sell problem, grounded in real user language from App Store reviews, Play Store
reviews, Reddit, forums, social media, and product reviews.

## Start here
- `CLAUDE.md` — project context Claude Code reads automatically. Open this folder in
  Claude Code (or run `claude` from inside it) and it has full context to start building.
- `docs/PROBLEM_STATEMENT.md` — the full problem statement, goals, requirements, and
  success criteria this project is scoped against.

## Quick start
1. Copy `.env.example` to `.env` and fill in your keys.
2. Open this folder in Claude Code: `cd blinkit-rag-chatbot && claude`
3. Ask it to start with ingestion — e.g. "set up the Apify ingestion scripts in
   `ingestion/` per CLAUDE.md."

## Layout
```
docs/            problem statement, requirements, open questions
ingestion/       Apify actor calls, n8n workflow exports, scraping scripts
processing/      embedding, clustering, theme/sentiment tagging
rag/             vector store setup, retrieval logic, chunking
app/             chat interface / API tying retrieval + Groq synthesis together
```
