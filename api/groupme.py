"""Read-only GroupMe v3 client.

Knows GroupMe's response envelope and nothing about our schema; translation
into rows lives in api/chat_store.py. Read-only by design - posting arrives in
GRPM-4 and belongs in a separate function with a separate credential.

GroupMe pages backward: you pass the oldest id you have seen as `before_id`
and get the 100 before that, newest-first. The end of history is a 304, not an
empty list.
"""

from typing import Iterator, Optional

import requests

from api.rate_limiter import get_rate_limiter

BASE_URL = "https://api.groupme.com/v3"
PAGE_LIMIT = 100
TIMEOUT = 30


class GroupMeError(Exception):
    """A GroupMe request failed."""


def fetch_message_page(group_id: str, token: str,
                       before_id: Optional[str] = None,
                       limit: int = PAGE_LIMIT) -> list[dict]:
    """One page of messages, newest first. Empty list at the end of history."""
    get_rate_limiter().wait_if_needed()

    params = {"token": token, "limit": limit}
    if before_id:
        params["before_id"] = before_id

    try:
        resp = requests.get(f"{BASE_URL}/groups/{group_id}/messages",
                            params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GroupMeError(f"GroupMe request failed: {exc}") from exc

    if resp.status_code == 304:
        return []
    if resp.status_code >= 400:
        raise GroupMeError(f"GroupMe returned HTTP {resp.status_code}")

    return resp.json()["response"]["messages"]


def iter_messages(group_id: str, token: str,
                  stop_before: Optional[str] = None,
                  max_pages: Optional[int] = None) -> Iterator[dict]:
    """Walk history backward, newest first.

    Args:
        stop_before: stop once this message id is reached. The poller passes
            the newest id it already has so it re-scans only a trailing window.
        max_pages: hard ceiling, so a bug cannot page forever.
    """
    before_id = None
    pages = 0

    while max_pages is None or pages < max_pages:
        page = fetch_message_page(group_id, token, before_id=before_id)
        if not page:
            return

        for message in page:
            if stop_before is not None and message["id"] == stop_before:
                return
            yield message

        before_id = page[-1]["id"]
        pages += 1
