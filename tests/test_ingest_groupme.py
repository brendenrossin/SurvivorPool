"""The GroupMe poller re-scans a trailing window.

Favorite counts rise after a message posts, so a poller that fetches only
messages newer than its high-water mark freezes every count at whatever it was
seconds after posting. It re-reads a trailing window instead and lets the
upsert refresh what changed.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from api.groupme import WalkState
from api.job_locks import LOCK_GROUPME_INGESTION, LOCK_INGESTION_AND_SCORING
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


def _ceiling_walk(*messages):
    """A walk the page ceiling truncated, as iter_messages reports it."""
    def walking(group_id, token, max_pages=None, walk=None, **kwargs):
        for message in messages:
            yield message
        walk.stopped_at_ceiling = True
    return walking


def test_ceiling_truncation_warns_and_is_not_a_success(job_db, monkeypatch, capsys):
    """The old detection inferred truncation from `total_seen >= MAX_RESCAN_PAGES
    * PAGE_LIMIT`, which is a guaranteed false negative whenever any page comes
    back short of PAGE_LIMIT - which GroupMe does routinely. WalkState is the
    only reliable signal.
    """
    monkeypatch.setattr(ingest_groupme, "iter_messages", _ceiling_walk(raw("m1")))
    ingest_groupme.run()

    out = capsys.readouterr().out
    assert "ceiling" in out
    assert "✅" not in out

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status != "success"
    assert meta.last_success_at is None
    # The window was not covered, but what it did fetch is still stored.
    assert job_db.query(ChatMessage).count() == 1


def test_no_ceiling_warning_when_history_simply_ran_out(job_db, monkeypatch, capsys):
    """One short page is the normal case, not a truncated walk."""
    def walking(group_id, token, max_pages=None, walk=None, **kwargs):
        yield raw("m1")
        # walk.stopped_at_ceiling stays False: iter_messages returns early when
        # a page comes back empty.

    monkeypatch.setattr(ingest_groupme, "iter_messages", walking)
    ingest_groupme.run()

    out = capsys.readouterr().out
    assert "ceiling" not in out
    assert "✅ GroupMe: 1 new, 0 refreshed" in out

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "success"


def test_no_ceiling_warning_when_the_window_edge_stopped_the_walk(job_db, monkeypatch,
                                                                 capsys):
    """Stopping at the cutoff abandons the generator before it can ever set the
    ceiling flag - the case the old heuristic got right and this must keep."""
    now = int(datetime.now(timezone.utc).timestamp())
    outside = now - int(timedelta(days=30).total_seconds())

    monkeypatch.setattr(
        ingest_groupme, "iter_messages",
        _ceiling_walk(raw("recent"), raw("old", created=outside)))
    ingest_groupme.run(days=14)

    assert "ceiling" not in capsys.readouterr().out


def test_run_passes_a_walk_state_to_the_client(job_db, monkeypatch):
    """Dropping the argument silently restores the false-negative heuristic."""
    seen = {}

    def capture(group_id, token, **kwargs):
        seen.update(kwargs)
        return iter([raw("m1")])

    monkeypatch.setattr(ingest_groupme, "iter_messages", capture)
    ingest_groupme.run()

    assert isinstance(seen["walk"], WalkState)


def test_run_takes_the_groupme_advisory_lock(job_db, monkeypatch):
    """Without it, a Railway retry firing while the previous run is still in
    flight collides on the message_id primary key mid-batch."""
    seen = []

    @contextmanager
    def fake_lock(db, lock_id, **kwargs):
        seen.append(lock_id)
        yield

    monkeypatch.setattr(ingest_groupme, "advisory_lock", fake_lock)
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1")]))
    ingest_groupme.run()

    assert seen == [LOCK_GROUPME_INGESTION]
    assert LOCK_GROUPME_INGESTION != LOCK_INGESTION_AND_SCORING


def test_a_busy_lock_is_skipped_not_an_error(job_db, monkeypatch):
    """A busy lock is normal operation, so it must not write an `error` row that
    masks a real failure from monitoring."""
    @contextmanager
    def busy(db, lock_id, **kwargs):
        raise RuntimeError(
            f"Could not acquire advisory lock {lock_id} - another job is running.")
        yield   # pragma: no cover

    monkeypatch.setattr(ingest_groupme, "advisory_lock", busy)
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: pytest.fail("must not fetch while locked"))

    assert ingest_groupme.run() == (0, 0)

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "skipped"
    assert meta.last_success_at is None


def test_a_failure_partway_through_keeps_committed_batches(job_db, monkeypatch):
    """The poller used to accumulate the whole trailing window - up to 5,000
    messages - into one list and one transaction, so a single bad row threw away
    the entire run's work."""
    monkeypatch.setattr(ingest_groupme, "BATCH_SIZE", 2)

    def walking(*a, **k):
        yield raw("m1")
        yield raw("m2")
        yield raw("m3")
        raise KeyError("envelope changed")

    monkeypatch.setattr(ingest_groupme, "iter_messages", walking)
    with pytest.raises(KeyError):
        ingest_groupme.run()

    # m1 and m2 committed as a full batch; m3 was still pending and rolled back.
    assert sorted(r.message_id for r in job_db.query(ChatMessage).all()) == ["m1", "m2"]
