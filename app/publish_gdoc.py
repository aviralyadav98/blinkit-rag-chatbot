"""
Phase 9 (companion) — publish the validated Insight Report to Google Docs.

UNATTENDED step: loads the refresh token minted once by `app/gdoc_auth.py`,
converts docs/INSIGHT_REPORT.md to a native Google Doc, and updates the SAME Doc
in place on every run (so the shareable link never changes). No browser, ever —
if the token is missing/invalid it fails with a clear "run gdoc_auth first"
message rather than trying to open a browser and hanging a headless scheduler.

    .venv/Scripts/python.exe app/publish_gdoc.py

Design:
  - Reads the already-generated + validated report file — it does NOT regenerate.
    Slotted into refresh.py AFTER validate.py passes, so only a report that cleared
    the groundedness/hallucination gate ever gets published.
  - Markdown -> HTML (markdown lib) -> Drive upload with
    mimeType=application/vnd.google-apps.document, which makes Drive convert HTML
    into a real Doc (headings, bold, bullets, links all carry over).
  - The Doc's fileId is persisted in app/.gdoc_state.json and reused via
    files.update, so weekly runs refresh one Doc instead of spawning a new one.
  - After (first) creation, the Doc is shared to GDOC_SHARE_EMAIL (writer, so you
    can annotate) — a service/OAuth-created file is invisible to you otherwise.
"""

import io
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_APP_DIR, ".."))
REPORT_PATH = os.path.join(_PROJECT_ROOT, "docs", "INSIGHT_REPORT.md")
TOKEN_PATH = os.getenv("GDOC_TOKEN_PATH", os.path.join(_APP_DIR, ".gdoc_token.json"))
STATE_PATH = os.path.join(_APP_DIR, ".gdoc_state.json")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DOC_TITLE = "Blinkit Category Cross-Sell — Insight Report"
SHARE_EMAIL = os.getenv("GDOC_SHARE_EMAIL", "")


class AuthNotReady(RuntimeError):
    """Token missing or unrefreshable — the one-time gdoc_auth step hasn't run."""


def _load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(TOKEN_PATH):
        raise AuthNotReady(
            f"No Google token at {TOKEN_PATH}. Run the one-time authorization first:\n"
            "    .venv/Scripts/python.exe app/gdoc_auth.py"
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise AuthNotReady(
                "Google token is invalid and cannot be refreshed (likely expired — "
                "this happens within 7 days if the OAuth consent screen is still in "
                "'Testing'. Move it to 'Production', then re-run app/gdoc_auth.py)."
            )
    return creds


def _markdown_to_html(md: str) -> str:
    import markdown

    body = markdown.markdown(md, extensions=["extra", "sane_lists"])
    # Wrap so Drive's HTML importer sees a full document with a title.
    return f"<html><head><meta charset='utf-8'><title>{DOC_TITLE}</title></head><body>{body}</body></html>"


def _read_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def publish() -> tuple[str, str]:
    """Create-or-update the report Doc. Returns (file_id, web_link)."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    if not os.path.exists(REPORT_PATH):
        raise FileNotFoundError(
            f"No report at {REPORT_PATH}. Generate it first (app/report_agent.py)."
        )

    with open(REPORT_PATH, encoding="utf-8") as f:
        html = _markdown_to_html(f.read())

    creds = _load_credentials()
    drive = build("drive", "v3", credentials=creds)
    media = MediaIoBaseUpload(io.BytesIO(html.encode("utf-8")), mimetype="text/html", resumable=False)

    state = _read_state()
    file_id = state.get("file_id")

    if file_id:
        try:
            drive.files().update(fileId=file_id, media_body=media).execute()
        except Exception as e:  # Doc was deleted / unshared out from under us
            print(f"[publish_gdoc] stored Doc {file_id} not updatable ({e}); creating a new one.")
            file_id = None

    if not file_id:
        created = drive.files().create(
            body={"name": DOC_TITLE, "mimeType": "application/vnd.google-apps.document"},
            media_body=media,
            fields="id",
        ).execute()
        file_id = created["id"]
        _write_state({"file_id": file_id})

        if SHARE_EMAIL:
            drive.permissions().create(
                fileId=file_id,
                body={"type": "user", "role": "writer", "emailAddress": SHARE_EMAIL},
                sendNotificationEmail=True,
                fields="id",
            ).execute()
            print(f"[publish_gdoc] shared with {SHARE_EMAIL} (writer).")
        else:
            print(
                "[publish_gdoc] GDOC_SHARE_EMAIL not set — Doc created but not shared, "
                "so it's only in the authorizing account's Drive. Set GDOC_SHARE_EMAIL "
                "to auto-share."
            )

    web_link = f"https://docs.google.com/document/d/{file_id}/edit"
    return file_id, web_link


def main() -> int:
    try:
        file_id, link = publish()
    except AuthNotReady as e:
        print(f"[publish_gdoc] {e}")
        return 2
    print(f"[publish_gdoc] published Doc {file_id}\n  {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
