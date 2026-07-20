"""Shared Apify client + actor-run helper used by every scraper in this package."""

import os

from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()


def get_client() -> ApifyClient:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set in .env")
    return ApifyClient(token)


def run_actor_and_get_items(actor_id: str, run_input: dict) -> list[dict]:
    """Runs an actor to completion and returns its default dataset items.

    This is the one place that actually spends money — every scraper module
    routes through here so a run is never triggered implicitly on import.
    """
    client = get_client()
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = run.default_dataset_id
    return list(client.dataset(dataset_id).iterate_items())
