"""The GroupMe poller re-scans a trailing window.

Favorite counts rise after a message posts, so a poller that fetches only
messages newer than its high-water mark freezes every count at whatever it was
seconds after posting. It re-reads a trailing window instead and lets the
upsert refresh what changed.
"""

from datetime import datetime, timedelta, timezone

import pytest

from api.models import ChatMessage, JobMeta
from jobs import ingest_groupme


def raw(mid, favs=0, created=None):
    # `created` defaults to "now" rather than a fixed epoch: run()'s trailing
    # window filters against the real wall clock, so a hardcoded timestamp
    # would fall outside the rescan window (and fail this test) once enough
    # real time has passed since that constant was chosen.
    if created is None:
        created = int(datetime.now(timezone.utc).timestamp())
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": ["x"] * favs, "created_at": created}


def test_run_persists_fetched_messages(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1"), raw("m2")]))
    inserted, updated = ingest_groupme.run()

    assert inserted == 2
    assert job_db.query(ChatMessage).count() == 2


def test_run_refreshes_favorite_counts_on_rescan(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", favs=1)]))
    ingest_groupme.run()

    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", favs=9)]))
    inserted, updated = ingest_groupme.run()

    assert (inserted, updated) == (0, 1)
    assert job_db.query(ChatMessage).one().favorite_count == 9


def test_run_records_success_in_job_meta(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages", lambda *a, **k: iter([raw("m1")]))
    ingest_groupme.run()

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "success"
    assert meta.last_success_at is not None


def test_run_records_error_and_reraises(job_db, monkeypatch):
    def boom(*a, **k):
        raise ingest_groupme.GroupMeError("token rejected")

    monkeypatch.setattr(ingest_groupme, "iter_messages", boom)
    with pytest.raises(ingest_groupme.GroupMeError):
        ingest_groupme.run()

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert meta.last_success_at is None


def test_unexpected_error_is_recorded_and_reraised(job_db, monkeypatch):
    """A GroupMe envelope change raises KeyError, not GroupMeError.

    The client and chat_store index ["response"], ["created_at"] and ["id"]
    directly, so a schema change used to escape the handler entirely and write
    NO job_meta row - leaving a stale `success` for monitoring to read while
    the job died in a Railway traceback nobody opens.
    """
    def boom(*a, **k):
        raise KeyError("super-secret-token-value")

    monkeypatch.setattr(ingest_groupme, "iter_messages", boom)
    with pytest.raises(KeyError):
        ingest_groupme.run()

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert meta.last_success_at is None
    assert "KeyError" in meta.message
    # The type name, never the payload: str(exc) on an arbitrary exception
    # could carry a token or a raw response body into job_meta and the logs.
    assert "super-secret-token-value" not in meta.message


def test_missing_credentials_is_a_clear_error(job_db, monkeypatch):
    monkeypatch.delenv("GROUPME_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GROUPME_ACCESS_TOKEN"):
        ingest_groupme.run()


def test_run_stops_at_the_trailing_window_edge(job_db, monkeypatch):
    """Proves the walk HALTS at the window edge, not merely that old messages
    are filtered out of the batch.

    The window is this job's whole design: re-read recent messages so their
    favorite counts refresh, then stop rather than re-walk the season against a
    rate-limited API. A materialized-list mock cannot show the difference -
    swapping `break` for `continue` passes it identically, because the
    out-of-window messages fail the cutoff check either way and never reach the
    batch. So this mock is a generator that records how far the walk actually
    got, mirroring test_backfill_stops_walking_at_the_since_date.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    inside = now - int(timedelta(days=1).total_seconds())
    outside = now - int(timedelta(days=30).total_seconds())

    consumed = []

    def walking(*a, **k):
        for message in [raw("recent", created=inside),
                        raw("old", created=outside),
                        raw("older", created=outside - 100)]:
            consumed.append(message["id"])
            yield message

    monkeypatch.setattr(ingest_groupme, "iter_messages", walking)

    inserted, _ = ingest_groupme.run(days=14)

    assert inserted == 1
    assert [r.message_id for r in job_db.query(ChatMessage).all()] == ["recent"]
    assert consumed == ["recent", "old"]   # halted at the first out-of-window message


def test_run_bounds_the_walk_with_a_page_ceiling(job_db, monkeypatch):
    """Without a ceiling, a cutoff that failed to fire would re-walk the whole
    group history every run against a rate-limited API."""
    seen = {}

    def capture(group_id, token, **kwargs):
        seen.update(kwargs)
        return iter([raw("m1")])

    monkeypatch.setattr(ingest_groupme, "iter_messages", capture)
    ingest_groupme.run()

    assert seen["max_pages"] == ingest_groupme.MAX_RESCAN_PAGES
