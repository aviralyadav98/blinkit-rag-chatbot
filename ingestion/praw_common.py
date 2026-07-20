"""Shared PRAW (Reddit) client helper.

Requires a free "script" app registered at reddit.com/prefs/apps — read-only
access to public data needs only client_id + client_secret, no username/password.
"""

import os

import praw
from dotenv import load_dotenv

load_dotenv()


def get_client() -> praw.Reddit:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "blinkit-rag-chatbot/0.1 (research script)")
    if not client_id or not client_secret:
        raise RuntimeError("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set in .env")
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
