"""Read-only GroupMe v3 client.

Knows GroupMe's response envelope and nothing about our schema; translation
into rows lives in api/chat_store.py. Read-only by design - posting arrives in
GRPM-4 and belongs in a separate function with a separate credential.

GroupMe pages backward: you pass the oldest id you have seen as `before_id`
and get the 100 before that, newest-first. The end of history is a 304, not an
empty list.

Authentication: token is sent as the X-Access-Token header, never in the URL.
This is UNVERIFIED - no live call has ever been made against this client, and
no credentials exist in this repo, so header auth remains an assumption until
Task 1's retention probe exercises it against the real API. If it turns out
unsupported, reverting to a `token` query param is a one-line change; the
redaction layer still protects logs from leaked secrets either way.
"""

import io
import os
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Iterator, Optional

import requests

from api.rate_limiter import APIRateLimiter

BASE_URL = "https://api.groupme.com/v3"
PAGE_LIMIT = 100
TIMEOUT = 30

# GroupMe's published guidance is far more generous than the 8 req/min the ESPN
# limiter defaults to - their v3 API is documented around 100 requests/minute
# per token. 30/min is a deliberately conservative fraction of that: it leaves
# ample headroom against an undocumented burst rule while keeping the backfill's
# 500-page ceiling to roughly 17 minutes of wall clock rather than an hour, which
# is the difference between a Railway one-off job finishing and being killed.
DEFAULT_MAX_REQUESTS_PER_MINUTE = 30

_rate_limiter: Optional[APIRateLimiter] = None


class GroupMeError(Exception):
    """A GroupMe request failed."""


@dataclass
class WalkState:
    """Why a history walk ended.

    Callers cannot otherwise distinguish a complete walk from one the page
    ceiling truncated - and for a backfill those mean very different things,
    since the truncated end is the OLDEST history.
    """
    pages: int = 0
    stopped_at_ceiling: bool = False


def _new_rate_limiter() -> APIRateLimiter:
    """Build GroupMe's own limiter from GROUPME_MAX_REQUESTS_PER_MINUTE.

    Deliberately not `api.rate_limiter.get_rate_limiter()`: that is a
    process-global singleton tuned by ESPN_API_MAX_REQUESTS_PER_MINUTE, so
    sharing it meant tuning ESPN silently retuned GroupMe, mislabelled every
    throttle line in the logs, and pinned the backfill to ESPN's 8 req/min -
    about an hour of blocking sleep for a 500-page walk.

    The class is reused as-is; only the instance is ours. Its constructor
    prints an "ESPN API Rate Limiter" banner, which would misattribute this
    limiter in exactly the way the split is meant to fix, so that line is
    swallowed and an accurate one printed in its place.
    """
    max_requests = int(os.getenv("GROUPME_MAX_REQUESTS_PER_MINUTE",
                                 str(DEFAULT_MAX_REQUESTS_PER_MINUTE)))
    with redirect_stdout(io.StringIO()):
        limiter = APIRateLimiter(max_requests)
    print(f"🛡️  GroupMe API Rate Limiter: {max_requests} req/min")
    return limiter


def _get_rate_limiter() -> APIRateLimiter:
    """GroupMe's limiter, built on first use.

    Lazily, so importing this module neither reads the environment nor prints.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = _new_rate_limiter()
    return _rate_limiter


def _redact(text: str, token: str) -> str:
    """Exception text with the token removed.

    Belt and braces: with header auth the token should never reach a URL, but
    this must not depend on that staying true. A leaked token would land in
    job_meta.message and Railway logs.
    """
    return text.replace(token, "***REDACTED***") if token else text


def fetch_message_page(group_id: str, token: str,
                       before_id: Optional[str] = None,
                       limit: int = PAGE_LIMIT) -> list[dict]:
    """One page of messages, newest first. Empty list at the end of history."""
    _get_rate_limiter().wait_if_needed()

    headers = {"X-Access-Token": token}
    params = {"limit": limit}
    if before_id:
        params["before_id"] = before_id

    try:
        resp = requests.get(f"{BASE_URL}/groups/{group_id}/messages",
                            params=params, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GroupMeError(f"GroupMe request failed: {_redact(str(exc), token)}") from exc

    if resp.status_code == 304:
        return []
    if resp.status_code >= 400:
        raise GroupMeError(f"GroupMe returned HTTP {resp.status_code}")

    return resp.json()["response"]["messages"]


def iter_messages(group_id: str, token: str,
                  stop_before: Optional[str] = None,
                  max_pages: Optional[int] = None,
                  walk: Optional[WalkState] = None) -> Iterator[dict]:
    """Walk history backward, newest first.

    Args:
        stop_before: stop as soon as this message id is yielded past - an
            id-based halt for a caller that already knows where its history
            begins. The poller does not use it: it filters on created_at
            instead, because favorite counts keep rising and a high-water mark
            would freeze every count at its value seconds after posting.
        max_pages: hard ceiling, so a bug cannot page forever.
        walk: optional WalkState, updated as the walk proceeds so the caller
            can tell a complete walk from one this ceiling truncated.
    """
    before_id = None
    pages = 0

    while max_pages is None or pages < max_pages:
        page = fetch_message_page(group_id, token, before_id=before_id)
        if not page:
            return          # history exhausted, not truncated

        pages += 1
        if walk is not None:
            walk.pages = pages

        for message in page:
            if stop_before is not None and message["id"] == stop_before:
                return      # caller's own stop condition, not truncation
            yield message

        before_id = page[-1]["id"]

    # Falling out of the loop is the one exit that means the ceiling stopped us.
    if walk is not None:
        walk.stopped_at_ceiling = True
