"""The GroupMe client pages backward through history.

GroupMe returns messages newest-first and signals "no more history" with a
304, not an empty list, so a client that only checks for `[]` walks forever.
"""

import pytest

from api import groupme


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
    """Unit tests must never sleep on the real limiter."""
    monkeypatch.setattr(groupme, "get_rate_limiter", lambda: type("_L", (), {"wait_if_needed": lambda self: True})())


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

    def fake_get(url, params=None, timeout=None):
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
