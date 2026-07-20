"""
Phase 9 (companion) — one-time Google OAuth authorization for Docs publishing.

This is the ONLY interactive step. It opens a browser once, you approve access,
and it writes a refresh-token file that `publish_gdoc.py` (and therefore the
unattended `refresh.py` pipeline) reuses forever after — no browser again.

    .venv/Scripts/python.exe app/gdoc_auth.py

Why separate from publish: `run_local_server()` opens a browser, which can never
run inside a headless scheduler (n8n/WSL2). Auth is a person-in-the-loop action;
publishing is not. Keeping them apart means the scheduled path never tries to
pop a browser and hang.

Prerequisites (one-time, all free):
  1. Google Cloud Console -> create a project (or reuse one).
  2. Enable the "Google Drive API".
  3. OAuth consent screen -> User type "External" -> add your Gmail as a Test user
     -> **then click "PUBLISH APP" to move it to "In production".**
     THIS MATTERS: while the consent screen is in "Testing", refresh tokens expire
     after 7 days and the weekly pipeline silently dies after one week. In
     "Production" (unverified is fine for your own account — you click through a
     one-time "unverified app" warning), the refresh token persists.
  4. Credentials -> Create OAuth client ID -> Application type "Desktop app" ->
     download the JSON. Point GOOGLE_OAUTH_CLIENT_SECRETS at it in .env.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# drive.file scope = least privilege: the app can only touch files IT created
# (our report Doc), not the user's whole Drive. It can still share those files.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS = os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", os.path.join(_APP_DIR, "client_secret.json"))
TOKEN_PATH = os.getenv("GDOC_TOKEN_PATH", os.path.join(_APP_DIR, ".gdoc_token.json"))


def main() -> int:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(CLIENT_SECRETS):
        print(
            f"OAuth client secrets not found at: {CLIENT_SECRETS}\n"
            "Create a Desktop-app OAuth client in Google Cloud Console, download the\n"
            "JSON, and set GOOGLE_OAUTH_CLIENT_SECRETS in .env to its path (see this\n"
            "file's docstring for the full one-time setup)."
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    # Opens a browser; user approves. access_type=offline + prompt=consent forces
    # a refresh_token to be issued (needed for later unattended refreshes).
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"Authorized. Refresh token saved to {TOKEN_PATH}")
    print("publish_gdoc.py (and refresh.py) can now publish unattended.")
    if not creds.refresh_token:
        print(
            "WARNING: no refresh_token was returned — unattended refresh will fail. "
            "Revoke access at myaccount.google.com/permissions and re-run this."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
