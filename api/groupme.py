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

import json
import os
import time
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

# A limiter set to zero or a negative number would either spin or block forever,
# so a misconfigured env var is clamped rather than honoured.
MIN_MAX_REQUESTS_PER_MINUTE = 1

# Retry budget. The real GroupMe rate limit is unverified (see the module
# docstring), which makes a 429 likely rather than hypothetical, and a backfill
# walk is hundreds of pages - one blip should not abort it. Three attempts with
# 1s then 2s of backoff is at most 3s of extra wall clock per page, which the
# rate limiter's own pacing already dwarfs.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0

# 429 is the only 4xx worth retrying; a 401 or a bad group id will fail exactly
# the same way on the next attempt, so those fail fast.
RETRYABLE_STATUS_CODES = frozenset({429})

# Enough of a failing response body to tell a revoked token from a bad group id,
# not enough to dump a page of HTML into job_meta.message.
ERROR_BODY_LIMIT = 200

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


def _sleep(seconds: float) -> None:
    """Indirection so tests can assert on backoff without spending it."""
    time.sleep(seconds)


def _max_requests_per_minute() -> int:
    """GROUPME_MAX_REQUESTS_PER_MINUTE, validated.

    A typo in a Railway variable should not crash the job with an unhandled
    ValueError, and a 0 or negative value should not be honoured: it would make
    the limiter wait out a full minute before every single request.
    """
    raw = os.getenv("GROUPME_MAX_REQUESTS_PER_MINUTE")
    if raw is None or not raw.strip():
        return DEFAULT_MAX_REQUESTS_PER_MINUTE

    try:
        value = int(raw.strip())
    except ValueError:
        print(f"⚠️  GROUPME_MAX_REQUESTS_PER_MINUTE={raw!r} is not an integer; "
              f"using the default of {DEFAULT_MAX_REQUESTS_PER_MINUTE} req/min")
        return DEFAULT_MAX_REQUESTS_PER_MINUTE

    if value < MIN_MAX_REQUESTS_PER_MINUTE:
        print(f"⚠️  GROUPME_MAX_REQUESTS_PER_MINUTE={value} is below the minimum; "
              f"clamping to {MIN_MAX_REQUESTS_PER_MINUTE} req/min")
        return MIN_MAX_REQUESTS_PER_MINUTE

    return value


def _new_rate_limiter() -> APIRateLimiter:
    """Build GroupMe's own limiter from GROUPME_MAX_REQUESTS_PER_MINUTE.

    Deliberately not `api.rate_limiter.get_rate_limiter()`: that is a
    process-global singleton tuned by ESPN_API_MAX_REQUESTS_PER_MINUTE, so
    sharing it meant tuning ESPN silently retuned GroupMe, mislabelled every
    throttle line in the logs, and pinned the backfill to ESPN's 8 req/min -
    about an hour of blocking sleep for a 500-page walk.

    The class is reused as-is; only the instance is ours. It takes the banner
    label as an argument so this limiter announces itself accurately instead of
    misattributing the limit to ESPN.
    """
    return APIRateLimiter(_max_requests_per_minute(), label="GroupMe API")


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


def _response_text(resp) -> str:
    try:
        return getattr(resp, "text", "") or ""
    except Exception:
        return ""


def _clip(text: str, token: str) -> str:
    """Redact first, then truncate.

    Order matters: truncating first can slice a token in half and leave the
    prefix behind, which redaction would then no longer recognise.
    """
    return _redact(text, token)[:ERROR_BODY_LIMIT].strip()


def _meta_error(body: str) -> Optional[str]:
    """GroupMe's documented error shape, or None if the body is not one.

    GroupMe answers a failure with {"meta": {"code": 401, "errors": [...]}}.
    Those two fields hold the entire diagnostic value of the response; the rest
    is free text from an external service that we would otherwise be writing
    verbatim into job_meta.message and Railway's hosted logs.
    """
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return None

    meta = payload.get("meta") if isinstance(payload, dict) else None
    if not isinstance(meta, dict):
        return None

    raw_errors = meta.get("errors")
    if isinstance(raw_errors, str):
        raw_errors = [raw_errors]
    if not isinstance(raw_errors, list):
        return None

    errors = [str(e) for e in raw_errors if isinstance(e, (str, int, float))]
    if not errors:
        return None

    detail = "; ".join(errors)
    code = meta.get("code")
    if isinstance(code, int):
        detail = f"{detail} (meta.code {code})"
    return detail


def _error_detail(resp, token: str) -> str:
    """A failing response as an operator-readable, redacted one-liner.

    The status code alone cannot distinguish a revoked token from a bad group
    id from a rejected auth scheme - all of which are live possibilities while
    header auth is unverified - so the body's diagnosis comes along.

    Preferably only the diagnosis: when the body is GroupMe's documented error
    envelope, this carries its meta.errors and meta.code and nothing else,
    because everything else in there is external free text on a path that runs
    only when something has already gone wrong. A body that is not that shape
    falls back to a capped slice of the raw text, since an HTML page from some
    proxy is itself the diagnosis. Both paths are redacted and capped - an
    error body is one of the places an API is most likely to echo a credential
    back at you.
    """
    body = _response_text(resp)
    detail = f"GroupMe returned HTTP {resp.status_code}"

    structured = _meta_error(body)
    if structured is not None:
        return f"{detail}: {_clip(structured, token)}"

    body = _clip(body, token)
    return f"{detail}: {body}" if body else detail


def _retry_after_seconds(resp) -> Optional[float]:
    """The Retry-After header in seconds, if it is present and usable."""
    if resp is None:
        return None
    headers = getattr(resp, "headers", None) or {}
    try:
        value = float(headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _retry_delay(attempt: int, resp=None) -> float:
    """Exponential backoff, overridden by Retry-After when the server sends one.

    Capped either way so a hostile or confused header cannot park a cron job
    for an hour.
    """
    delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    retry_after = _retry_after_seconds(resp)
    if retry_after is not None:
        delay = retry_after
    return min(delay, MAX_BACKOFF_SECONDS)


def _is_retryable(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def fetch_message_page(group_id: str, token: str,
                       before_id: Optional[str] = None,
                       limit: int = PAGE_LIMIT) -> list[dict]:
    """One page of messages, newest first. Empty list at the end of history.

    Retries 429s, 5xx and connection errors a bounded number of times; every
    other 4xx fails immediately, since a 401 or a bad group id will fail
    identically on the next attempt.
    """
    headers = {"X-Access-Token": token}
    params = {"limit": limit}
    if before_id:
        params["before_id"] = before_id

    for attempt in range(1, MAX_ATTEMPTS + 1):
        _get_rate_limiter().wait_if_needed()

        try:
            # allow_redirects=False because X-Access-Token is a custom header:
            # requests strips the standard Authorization header on a cross-host
            # redirect but forwards custom ones verbatim, so a redirect to any
            # host would hand that host a long-lived credential that can read
            # every group its owner belongs to. The messages endpoint has no
            # legitimate reason to redirect.
            resp = requests.get(f"{BASE_URL}/groups/{group_id}/messages",
                                params=params, headers=headers, timeout=TIMEOUT,
                                allow_redirects=False)
        except requests.RequestException as exc:
            if attempt < MAX_ATTEMPTS:
                _sleep(_retry_delay(attempt))
                continue
            raise GroupMeError(
                f"GroupMe request failed: {_redact(str(exc), token)}") from exc

        if resp.status_code == 304:
            return []

        if 300 <= resp.status_code < 400:
            # Not followed, on purpose - see the allow_redirects comment above.
            raise GroupMeError(
                f"GroupMe redirected (HTTP {resp.status_code}); not followed, "
                f"because doing so would forward the access token to another host")

        if resp.status_code >= 400:
            if _is_retryable(resp.status_code) and attempt < MAX_ATTEMPTS:
                _sleep(_retry_delay(attempt, resp))
                continue
            raise GroupMeError(_error_detail(resp, token))

        return resp.json()["response"]["messages"]

    # Unreachable: the final attempt either returns or raises above.
    raise GroupMeError("GroupMe request failed after retries")


def iter_messages(group_id: str, token: str,
                  max_pages: Optional[int] = None,
                  walk: Optional[WalkState] = None) -> Iterator[dict]:
    """Walk history backward, newest first.

    There is deliberately no id-based stop condition. Both callers filter on
    created_at instead, because favorite counts keep rising and a high-water
    mark would freeze every count at its value seconds after posting.

    Args:
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
            yield message

        before_id = page[-1]["id"]

    # Falling out of the loop is the one exit that means the ceiling stopped us.
    if walk is not None:
        walk.stopped_at_ceiling = True
