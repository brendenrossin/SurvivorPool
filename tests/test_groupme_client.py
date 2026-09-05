"""The GroupMe client pages backward through history.

GroupMe returns messages newest-first and signals "no more history" with a
304, not an empty list, so a client that only checks for `[]` walks forever.
"""

from pathlib import Path

import pytest

from api import groupme, rate_limiter


class FakeResponse:
    def __init__(self, status_code, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


def _page(ids):
    return {"response": {"messages": [
        {"id": i, "group_id": "g1", "user_id": "u1", "name": "Someone",
         "sender_type": "user", "text": f"msg {i}", "system": False,
         "favorited_by": [], "created_at": 1700000000}
        for i in ids
    ]}}


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """Unit tests must never sleep on the real limiter.

    GroupMe builds its own limiter now rather than borrowing ESPN's global
    singleton, so the patch target is the module-local accessor. The tests that
    exercise the limiter itself call `_new_rate_limiter` directly, which this
    leaves alone.
    """
    monkeypatch.setattr(groupme, "_get_rate_limiter", lambda: type("_L", (), {"wait_if_needed": lambda self: True})())


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Backoff is recorded, never spent - no test may sleep."""
    recorded = []
    monkeypatch.setattr(groupme, "_sleep", recorded.append)
    return recorded


def test_fetch_message_page_returns_messages(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["3", "2", "1"])))
    out = groupme.fetch_message_page("g1", "tok")
    assert [m["id"] for m in out] == ["3", "2", "1"]


def test_304_means_end_of_history(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: FakeResponse(304))
    assert groupme.fetch_message_page("g1", "tok", before_id="1") == []


def test_iter_messages_pages_backward_until_exhausted(monkeypatch):
    pages = [_page(["5", "4"]), _page(["3", "2"]), None]
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append(params.get("before_id"))
        nxt = pages.pop(0)
        return FakeResponse(200, nxt) if nxt else FakeResponse(304)

    monkeypatch.setattr(groupme.requests, "get", fake_get)
    ids = [m["id"] for m in groupme.iter_messages("g1", "tok")]
    assert ids == ["5", "4", "3", "2"]
    assert calls == [None, "4", "2"]   # before_id is the oldest id of the prior page


def test_http_error_raises_groupme_error(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: FakeResponse(500))
    with pytest.raises(groupme.GroupMeError):
        groupme.fetch_message_page("g1", "tok")


def test_token_never_appears_in_a_raised_error(monkeypatch):
    """A leaked token would be written to job_meta.message and Railway logs."""
    secret = "super-secret-token-value"

    def boom(*a, **k):
        raise groupme.requests.RequestException(
            f"Max retries exceeded with url: /v3/groups/g1/messages?token={secret}")

    monkeypatch.setattr(groupme.requests, "get", boom)
    with pytest.raises(groupme.GroupMeError) as err:
        groupme.fetch_message_page("g1", secret)
    assert secret not in str(err.value)


def test_token_is_sent_as_a_header_not_a_query_param(monkeypatch):
    """Keeping the secret out of the URL keeps it out of every log that records one."""
    seen = {}

    def capture(url, params=None, headers=None, **kwargs):
        seen["params"] = params
        seen["headers"] = headers
        return FakeResponse(200, _page(["1"]))

    monkeypatch.setattr(groupme.requests, "get", capture)
    groupme.fetch_message_page("g1", "tok")

    assert "token" not in (seen["params"] or {})
    assert seen["headers"]["X-Access-Token"] == "tok"


def test_redirects_are_not_followed(monkeypatch):
    """X-Access-Token is a custom header, so requests would forward it verbatim
    to whatever host a redirect names - unlike Authorization, which it strips.
    That token can read every group its owner belongs to."""
    seen = {}

    def capture(url, **kwargs):
        seen.update(kwargs)
        return FakeResponse(200, _page(["1"]))

    monkeypatch.setattr(groupme.requests, "get", capture)
    groupme.fetch_message_page("g1", "tok")

    assert seen["allow_redirects"] is False


def test_a_redirect_response_is_an_error_not_a_parse_attempt(monkeypatch):
    """With redirects unfollowed, a 302 arrives as a response with no envelope."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(302, headers={"Location": "http://evil"}))
    with pytest.raises(groupme.GroupMeError) as err:
        groupme.fetch_message_page("g1", "tok")
    assert "302" in str(err.value)


def test_error_body_is_included_for_the_operator(monkeypatch):
    """HTTP 401 alone cannot distinguish a revoked token from a rejected auth
    scheme, and header auth here is still unverified."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(401, text='{"meta":{"errors":["unauthorized"]}}'))
    with pytest.raises(groupme.GroupMeError) as err:
        groupme.fetch_message_page("g1", "tok")
    assert "401" in str(err.value)
    assert "unauthorized" in str(err.value)


def test_a_token_echoed_in_an_error_body_is_redacted(monkeypatch):
    """An API echoing the credential back is exactly how a body leaks a secret."""
    secret = "super-secret-token-value"
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(
                            403, text=f'{{"error":"bad token {secret}"}}'))
    with pytest.raises(groupme.GroupMeError) as err:
        groupme.fetch_message_page("g1", secret)
    assert secret not in str(err.value)
    assert "REDACTED" in str(err.value)


def test_error_body_is_capped(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(500, text="x" * 5000))
    with pytest.raises(groupme.GroupMeError) as err:
        groupme.fetch_message_page("g1", "tok")
    assert len(str(err.value)) < groupme.ERROR_BODY_LIMIT + 100


def test_429_is_retried_then_succeeds(monkeypatch, sleeps):
    """The real GroupMe rate limit is unverified, so a 429 is likely rather
    than hypothetical, and one must not abort a hundreds-of-pages walk."""
    responses = [FakeResponse(429), FakeResponse(200, _page(["1"]))]
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: responses.pop(0))

    assert [m["id"] for m in groupme.fetch_message_page("g1", "tok")] == ["1"]
    assert len(sleeps) == 1


def test_5xx_is_retried_then_gives_up_as_groupme_error(monkeypatch, sleeps):
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: FakeResponse(503))

    with pytest.raises(groupme.GroupMeError):
        groupme.fetch_message_page("g1", "tok")

    assert len(sleeps) == groupme.MAX_ATTEMPTS - 1
    assert sleeps == sorted(sleeps)                      # backoff, not a fixed pause
    assert sum(sleeps) <= groupme.MAX_BACKOFF_SECONDS * groupme.MAX_ATTEMPTS


def test_connection_errors_are_retried(monkeypatch, sleeps):
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise groupme.requests.ConnectionError("connection reset")
        return FakeResponse(200, _page(["1"]))

    monkeypatch.setattr(groupme.requests, "get", flaky)

    assert [m["id"] for m in groupme.fetch_message_page("g1", "tok")] == ["1"]
    assert len(sleeps) == 1


def test_401_fails_fast_without_retrying(monkeypatch, sleeps):
    """A revoked token fails identically on every attempt; retrying only delays
    the job's failure and burns quota."""
    calls = []

    def counted(*a, **k):
        calls.append(1)
        return FakeResponse(401, text="unauthorized")

    monkeypatch.setattr(groupme.requests, "get", counted)

    with pytest.raises(groupme.GroupMeError):
        groupme.fetch_message_page("g1", "tok")

    assert len(calls) == 1
    assert sleeps == []


def test_retry_after_header_is_honoured(monkeypatch, sleeps):
    responses = [FakeResponse(429, headers={"Retry-After": "5"}),
                 FakeResponse(200, _page(["1"]))]
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: responses.pop(0))

    groupme.fetch_message_page("g1", "tok")

    assert sleeps == [5.0]


def test_a_wild_retry_after_cannot_park_the_job(monkeypatch, sleeps):
    """A cron job parked for an hour on a header value is an outage."""
    responses = [FakeResponse(429, headers={"Retry-After": "3600"}),
                 FakeResponse(200, _page(["1"]))]
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: responses.pop(0))

    groupme.fetch_message_page("g1", "tok")

    assert sleeps == [groupme.MAX_BACKOFF_SECONDS]


def test_a_garbage_retry_after_falls_back_to_backoff(monkeypatch, sleeps):
    responses = [FakeResponse(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
                 FakeResponse(200, _page(["1"]))]
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: responses.pop(0))

    groupme.fetch_message_page("g1", "tok")

    assert sleeps == [groupme.BACKOFF_BASE_SECONDS]


def test_groupme_does_not_share_espns_rate_limiter(monkeypatch):
    """Sharing the ESPN singleton meant ESPN_API_MAX_REQUESTS_PER_MINUTE
    silently retuned GroupMe, and pinned the backfill to 8 req/min - roughly an
    hour of blocking sleep for a 500-page walk."""
    monkeypatch.setenv("ESPN_API_MAX_REQUESTS_PER_MINUTE", "3")
    monkeypatch.delenv("GROUPME_MAX_REQUESTS_PER_MINUTE", raising=False)

    limiter = groupme._new_rate_limiter()

    assert limiter is not rate_limiter.get_rate_limiter()
    assert limiter.max_requests_per_minute == groupme.DEFAULT_MAX_REQUESTS_PER_MINUTE
    assert groupme.DEFAULT_MAX_REQUESTS_PER_MINUTE > 8


def test_groupme_limiter_reads_its_own_env_var(monkeypatch):
    monkeypatch.setenv("GROUPME_MAX_REQUESTS_PER_MINUTE", "42")
    assert groupme._new_rate_limiter().max_requests_per_minute == 42


def test_the_limiter_banner_names_groupme(monkeypatch, capsys):
    """The whole point of the split is that throttle lines are attributable."""
    monkeypatch.delenv("GROUPME_MAX_REQUESTS_PER_MINUTE", raising=False)
    groupme._new_rate_limiter()

    out = capsys.readouterr().out
    assert "GroupMe API Rate Limiter" in out
    assert "ESPN" not in out


def test_espn_limiter_banner_is_unchanged():
    """The label defaults to ESPN so every existing caller prints as before."""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rate_limiter.APIRateLimiter(8, 300)

    assert buf.getvalue() == "🛡️  ESPN API Rate Limiter: 8 req/min, 300s cache\n"


def test_a_malformed_rate_limit_env_var_falls_back_to_the_default(monkeypatch, capsys):
    """A Railway typo should not crash the cron with an unhandled ValueError."""
    monkeypatch.setenv("GROUPME_MAX_REQUESTS_PER_MINUTE", "thirty")

    limiter = groupme._new_rate_limiter()

    assert limiter.max_requests_per_minute == groupme.DEFAULT_MAX_REQUESTS_PER_MINUTE
    assert "GROUPME_MAX_REQUESTS_PER_MINUTE" in capsys.readouterr().out


def test_a_nonpositive_rate_limit_is_clamped(monkeypatch, capsys):
    """0 req/min makes the limiter wait out a full minute before every request."""
    monkeypatch.setenv("GROUPME_MAX_REQUESTS_PER_MINUTE", "0")

    limiter = groupme._new_rate_limiter()

    assert limiter.max_requests_per_minute == groupme.MIN_MAX_REQUESTS_PER_MINUTE
    assert "clamping" in capsys.readouterr().out


def test_importing_the_module_builds_no_limiter():
    """A limiter built at import time would read env and print on every import,
    and would be constructed before the no-op fixture could patch it away.

    Checked in a fresh interpreter because this module's global outlives any
    single test in this process. No network: it only imports.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import api.groupme as g; print(g._rate_limiter)"],
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "None"


def test_walk_state_reports_a_complete_walk(monkeypatch):
    """Exhausted history is not truncation - the backfill claims success here."""
    pages = [_page(["5", "4"]), None]

    def fake_get(url, **kwargs):
        nxt = pages.pop(0)
        return FakeResponse(200, nxt) if nxt else FakeResponse(304)

    monkeypatch.setattr(groupme.requests, "get", fake_get)
    walk = groupme.WalkState()

    assert [m["id"] for m in groupme.iter_messages("g1", "tok", walk=walk)] == ["5", "4"]
    assert walk.stopped_at_ceiling is False
    assert walk.pages == 1


def test_walk_state_reports_the_page_ceiling(monkeypatch):
    """The caller cannot otherwise tell a full walk from a truncated one, and
    for a backfill the truncated end is the oldest history."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8"])))
    walk = groupme.WalkState()

    list(groupme.iter_messages("g1", "tok", max_pages=2, walk=walk))

    assert walk.stopped_at_ceiling is True
    assert walk.pages == 2


def test_iter_messages_without_a_walk_behaves_as_before(monkeypatch):
    """`walk` is optional; existing callers pass nothing."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8"])))
    assert [m["id"] for m in groupme.iter_messages("g1", "tok", max_pages=1)] == ["9", "8"]
