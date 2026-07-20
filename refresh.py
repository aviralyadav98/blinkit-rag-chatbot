"""
Phase 8 — Refresh pipeline (docs/IMPLEMENTATION.md Phase 8).

One command that runs the whole flow end-to-end so the corpus and report stay
current: ingest -> process (incremental embed + cluster + label + store) ->
load Chroma -> generate report -> validate. This is exactly what the n8n weekly
schedule would trigger; standing n8n up (the scheduler wrapper) is the one piece
still blocked on the local WSL2/Docker setup, so for now this is run manually or
from any OS-level scheduler.

    .venv/Scripts/python.exe refresh.py [--skip-ingest] [--reembed]

Design notes:
  - Embedding is incremental (processing/run_processing.py): a refresh on a grown
    corpus only embeds NEW chunks, so cost scales with new data, not total size
    (CLAUDE.md: cost sub-linear with corpus growth).
  - Each stage is a normal re-runnable module; dedup on source_url / chunk text
    means re-running is safe and idempotent.
  - --skip-ingest reprocesses the existing raw corpus without re-scraping (useful
    when only code/params changed). --reembed forces a full re-embed.
  - The report step honors SYNTHESIS_MODEL (unset -> 70b).
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable


def _step(name: str, script_rel: str, args: list[str] | None = None, cwd_rel: str = ".") -> None:
    print(f"\n{'=' * 60}\n[refresh] {name}\n{'=' * 60}")
    cmd = [PY, os.path.join(ROOT, script_rel), *(args or [])]
    result = subprocess.run(cmd, cwd=os.path.join(ROOT, cwd_rel))
    if result.returncode != 0:
        raise SystemExit(f"[refresh] step '{name}' failed (exit {result.returncode}) — aborting refresh.")


def main() -> int:
    skip_ingest = "--skip-ingest" in sys.argv
    reembed = ["--reembed"] if "--reembed" in sys.argv else []

    if not skip_ingest:
        _step("1/5 Ingest (free-tier scrapers)", "ingestion/run_ingestion.py", cwd_rel="ingestion")
    else:
        print("[refresh] skipping ingest (--skip-ingest); reprocessing existing raw corpus")

    _step("2/6 Process (incremental embed -> cluster -> label -> store)",
          "processing/run_processing.py", args=reembed, cwd_rel="processing")
    _step("3/6 Load Chroma", "rag/load_chroma.py", cwd_rel="rag")
    _step("4/6 Generate report (Layer 1)", "app/report_agent.py", cwd_rel="app")
    _step("5/6 Validate (Phase 6 gate)", "app/validate.py", cwd_rel="app")

    # Publish to Google Docs AFTER validation passes (a step 5 failure aborts before
    # we get here), so only a report that cleared the groundedness gate is published.
    # Opt-in: skipped silently unless a Google token exists, so the core pipeline
    # never depends on the Docs integration being set up.
    token_path = os.getenv("GDOC_TOKEN_PATH", os.path.join(ROOT, "app", ".gdoc_token.json"))
    if os.path.exists(token_path):
        _step("6/6 Publish report to Google Docs", "app/publish_gdoc.py", cwd_rel="app")
    else:
        print("\n[refresh] 6/6 Google Docs publish — skipped (no token; run app/gdoc_auth.py once to enable).")

    print(f"\n{'=' * 60}\n[refresh] complete — corpus reprocessed, report regenerated and validated.")
    print("A scheduled run that grows the corpus and still clears the validation gate")
    print("is Phase 8's exit criterion; the only missing piece is the cron trigger (n8n).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
