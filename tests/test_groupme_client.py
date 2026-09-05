"""The GroupMe client pages backward through history.

GroupMe returns messages newest-first and signals "no more history" with a
304, not an empty list, so a client that only checks for `[]` walks forever.
"""

from pathlib import Path

import pytest

from api import groupme, rate_limiter


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

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

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(params.get("before_id"))
        nxt = pages.pop(0)
        return FakeResponse(200, nxt) if nxt else FakeResponse(304)

    monkeypatch.setattr(groupme.requests, "get", fake_get)
    ids = [m["id"] for m in groupme.iter_messages("g1", "tok")]
    assert ids == ["5", "4", "3", "2"]
    assert calls == [None, "4", "2"]   # before_id is the oldest id of the prior page


def test_iter_messages_stops_at_stop_before(monkeypatch):
    """The poller only re-scans a trailing window; it must not walk all history."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8", "7"])))
    ids = [m["id"] for m in groupme.iter_messages("g1", "tok", stop_before="8")]
    assert ids == ["9"]


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

    def capture(url, params=None, headers=None, timeout=None):
        seen["params"] = params
        seen["headers"] = headers
        return FakeResponse(200, _page(["1"]))

    monkeypatch.setattr(groupme.requests, "get", capture)
    groupme.fetch_message_page("g1", "tok")

    assert "token" not in (seen["params"] or {})
    assert seen["headers"]["X-Access-Token"] == "tok"


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

    def fake_get(url, params=None, headers=None, timeout=None):
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


def test_stop_before_is_not_reported_as_truncation(monkeypatch):
    """Halting on the caller's own stop condition is a complete walk."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8", "7"])))
    walk = groupme.WalkState()

    list(groupme.iter_messages("g1", "tok", stop_before="8", max_pages=1, walk=walk))

    assert walk.stopped_at_ceiling is False


def test_iter_messages_without_a_walk_behaves_as_before(monkeypatch):
    """`walk` is optional; existing callers pass nothing."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8"])))
    assert [m["id"] for m in groupme.iter_messages("g1", "tok", max_pages=1)] == ["9", "8"]
