"""One-time walk back through GroupMe history.

The chat's membership tracks the surviving field (252 in week 1, 22 by week
14), so volume decays across the season and this is a smaller job than a
252-person chat implies. It still needs a hard page ceiling: paging backward
forever on an unexpected response shape is the failure mode that burns the
rate limit.
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from api.groupme import WalkState
from api.job_locks import (LOCK_GROUPME_INGESTION, LOCK_INGESTION_AND_SCORING,
                           LockContentionError)
from api.models import ChatMessage, JobMeta
from jobs import backfill_groupme


def raw(mid, created):
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": [], "created_at": created}


SEP_2025 = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp())
AUG_2025 = int(datetime(2025, 8, 1, tzinfo=timezone.utc).timestamp())


def test_backfill_stops_walking_at_the_since_date(job_db, monkeypatch):
    """Proves the walk HALTS, not merely that old messages are filtered.

    The rate limit is why this matters: `since` and the page ceiling are the
    only stop conditions, so a filter-but-keep-walking bug would drag the whole
    group history through the API every run. A materialized-list mock cannot
    show the difference - swapping `break` for `continue` passes it
    identically - so this mock is a generator that records how far it got.
    """
    consumed = []

    def walking(*a, **k):
        for message in [raw("m3", SEP_2025),
                        raw("m2", AUG_2025),
                        raw("m1", AUG_2025 - 100)]:
            consumed.append(message["id"])
            yield message

    monkeypatch.setattr(backfill_groupme, "iter_messages", walking)

    inserted, updated = backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert (inserted, updated) == (1, 0)
    assert consumed == ["m3", "m2"]   # halted at the first out-of-range message


def test_backfill_bounds_the_walk_with_a_page_ceiling(job_db, monkeypatch):
    """A dropped max_pages would let a bad --since walk the entire history."""
    seen = {}

    def capture(group_id, token, **kwargs):
        seen.update(kwargs)
        return iter([raw("m1", SEP_2025)])

    monkeypatch.setattr(backfill_groupme, "iter_messages", capture)
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert seen["max_pages"] == backfill_groupme.MAX_PAGES


def test_backfill_returns_zero_on_empty_history(job_db, monkeypatch):
    monkeypatch.setattr(backfill_groupme, "iter_messages", lambda *a, **k: iter([]))
    assert backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc)) == (0, 0)


def test_truncated_backfill_does_not_claim_success(job_db, monkeypatch, capsys):
    """The page ceiling cutting the walk short is not a completed backfill.

    What is missing is the OLDEST end of the range - early-season history, when
    the group had 252 members rather than 22, which is the highest-value part
    of the voice corpus.
    """
    def walking(group_id, token, max_pages=None, walk=None, **kwargs):
        yield raw("m1", SEP_2025)
        walk.stopped_at_ceiling = True      # as iter_messages does at the ceiling
        walk.pages = max_pages

    monkeypatch.setattr(backfill_groupme, "iter_messages", walking)
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    out = capsys.readouterr().out
    assert "✅" not in out
    assert "INCOMPLETE" in out
    assert "--max-pages" in out


def test_complete_backfill_still_reports_success(job_db, monkeypatch, capsys):
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", SEP_2025)]))
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert "✅ Backfilled 1 new, 0 re-seen" in capsys.readouterr().out


def test_backfill_passes_a_walk_state_to_the_client(job_db, monkeypatch):
    """WalkState is the only way the job can tell truncation from completion,
    so dropping the argument would silently restore the false success line."""
    seen = {}

    def capture(group_id, token, **kwargs):
        seen.update(kwargs)
        return iter([raw("m1", SEP_2025)])

    monkeypatch.setattr(backfill_groupme, "iter_messages", capture)
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert isinstance(seen["walk"], WalkState)


def test_since_with_an_offset_is_converted_not_relabelled():
    """.replace(tzinfo=utc) relabels: a Pacific midnight silently became a UTC
    midnight, moving the boundary seven hours and dropping real history."""
    assert backfill_groupme._parse_since("2025-09-01T00:00:00-07:00") == \
        datetime(2025, 9, 1, 7, 0, tzinfo=timezone.utc)


def test_a_naive_since_is_read_as_utc():
    """The default --since is a bare date, which has no offset to convert."""
    assert backfill_groupme._parse_since("2025-09-01") == \
        datetime(2025, 9, 1, tzinfo=timezone.utc)


def test_backfill_reports_new_and_re_seen_separately(job_db, monkeypatch, capsys):
    """A re-run over overlapping history is mostly re-touched rows.

    The old return value was inserted + updated, so the second run of the same
    range reported the same headline number as the first and an operator could
    not tell real progress from re-scan noise.

    "re-seen", not "refreshed": upsert_messages() re-writes every row it
    matches and cannot tell an actual change from an identical re-scan, so the
    second number counts rows matched, not rows whose content moved.
    """
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", SEP_2025),
                                              raw("m2", SEP_2025 + 1)]))
    since = datetime(2025, 9, 1, tzinfo=timezone.utc)

    assert backfill_groupme.backfill(since=since) == (2, 0)
    capsys.readouterr()

    assert backfill_groupme.backfill(since=since) == (0, 2)
    assert "0 new, 2 re-seen" in capsys.readouterr().out


def test_backfill_records_success_in_job_meta(job_db, monkeypatch):
    """Nothing recorded this job at all before, so a run that died halfway left
    no trace of how far it got."""
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", SEP_2025)]))
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "success"
    assert meta.last_success_at is not None


def test_truncated_backfill_is_not_recorded_as_success(job_db, monkeypatch):
    """The page ceiling cutting the walk short must not advance last_success_at:
    the oldest end of the requested range was never fetched."""
    def walking(group_id, token, max_pages=None, walk=None, **kwargs):
        yield raw("m1", SEP_2025)
        walk.stopped_at_ceiling = True      # as iter_messages does at the ceiling

    monkeypatch.setattr(backfill_groupme, "iter_messages", walking)
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    # "incomplete", deliberately NOT the poller's success-with-a-caveat: for a
    # backfill the truncated end is history that is genuinely missing.
    assert meta.status == backfill_groupme.STATUS_INCOMPLETE
    assert meta.last_success_at is None
    assert "ceiling" in meta.message
    # The rows it did fetch are still stored - truncated, not discarded.
    assert job_db.query(ChatMessage).count() == 1


def test_backfill_records_a_groupme_error_and_reraises(job_db, monkeypatch):
    def boom(*a, **k):
        raise backfill_groupme.GroupMeError("GroupMe returned HTTP 401")

    monkeypatch.setattr(backfill_groupme, "iter_messages", boom)
    with pytest.raises(backfill_groupme.GroupMeError):
        backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert meta.last_success_at is None


def test_backfill_records_an_unexpected_error_without_leaking_it(job_db, monkeypatch):
    """A changed GroupMe envelope raises KeyError mid-walk. That used to crash
    the backfill with a raw traceback and no job_meta row at all."""
    def walking(*a, **k):
        yield raw("m1", SEP_2025)
        raise KeyError("super-secret-token-value")

    monkeypatch.setattr(backfill_groupme, "iter_messages", walking)
    with pytest.raises(KeyError):
        backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert meta.last_success_at is None
    assert "KeyError" in meta.message
    assert "super-secret-token-value" not in meta.message


def test_backfill_takes_the_groupme_advisory_lock(job_db, monkeypatch):
    """Without it, a manual backfill overlapping the poller's cron collides on
    the message_id primary key mid-batch."""
    seen = []

    @contextmanager
    def fake_lock(db, lock_id, **kwargs):
        seen.append(lock_id)
        yield

    monkeypatch.setattr(backfill_groupme, "advisory_lock", fake_lock)
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", SEP_2025)]))
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert seen == [LOCK_GROUPME_INGESTION]
    assert LOCK_GROUPME_INGESTION != LOCK_INGESTION_AND_SCORING


@contextmanager
def _busy_lock(db, lock_id, **kwargs):
    # The real type api/job_locks.py raises, not a hand-written RuntimeError
    # carrying a copy of its message.
    raise LockContentionError(
        f"Could not acquire advisory lock {lock_id} - another job is running.")
    yield   # pragma: no cover


def test_a_busy_lock_is_skipped_not_an_error(job_db, monkeypatch):
    """A busy lock is normal operation - the other run is doing the work - so
    it must not write an `error` row that masks a real failure."""
    monkeypatch.setattr(backfill_groupme, "advisory_lock", _busy_lock)
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: pytest.fail("must not fetch while locked"))

    assert backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc)) is None

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "skipped"
    assert meta.last_success_at is None


def test_a_busy_lock_tells_the_operator_it_did_not_run(job_db, monkeypatch,
                                                       capsys):
    """This is a one-shot somebody typed and is waiting on, not a cron.

    "will retry next run" - correct for the poller - was a straight lie here:
    nothing was backfilled and nothing will be until a human runs it again.
    """
    monkeypatch.setattr(backfill_groupme, "advisory_lock", _busy_lock)
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: pytest.fail("must not fetch while locked"))
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert "did not run" in meta.message
    assert "Re-run" in meta.message
    assert "retry next run" not in meta.message
    assert "DID NOT RUN" in capsys.readouterr().out


def test_a_busy_lock_exits_non_zero(job_db, monkeypatch):
    """`python jobs/backfill_groupme.py && echo done` printed `done` after a
    run that never happened - __main__ threw the return value away."""
    monkeypatch.setattr(backfill_groupme, "advisory_lock", _busy_lock)
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: pytest.fail("must not fetch while locked"))

    assert backfill_groupme.main(["--since", "2025-09-01"]) == 1


def test_a_backfill_that_ran_exits_zero(job_db, monkeypatch):
    """(0, 0) means it ran and found nothing - a different thing from not
    running at all, and the reason contention returns None."""
    monkeypatch.setattr(backfill_groupme, "iter_messages", lambda *a, **k: iter([]))

    assert backfill_groupme.main(["--since", "2025-09-01"]) == 0


def test_missing_credentials_is_recorded_and_reraised(job_db, monkeypatch):
    """The credential check used to run before the session was opened, so a
    revoked GROUPME_ACCESS_TOKEN left no job_meta row at all."""
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "super-secret-token-value")
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", SEP_2025)]))
    backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))
    before = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one().last_success_at
    assert before is not None

    monkeypatch.delenv("GROUPME_ACCESS_TOKEN")
    monkeypatch.setattr(
        backfill_groupme, "iter_messages",
        lambda *a, **k: pytest.fail("must not fetch without credentials"))
    with pytest.raises(backfill_groupme.ConfigurationError,
                       match="GROUPME_ACCESS_TOKEN"):
        backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert "GROUPME_ACCESS_TOKEN" in meta.message
    # Names the variable, never its value: this is the credential path.
    assert "super-secret-token-value" not in meta.message
    assert meta.last_success_at == before


def test_a_naive_since_is_rejected_and_recorded(job_db):
    """The naive/aware comparison would otherwise raise TypeError mid-walk,
    after batches had already committed.

    Same shape as the credential failure, and folded in with it: the check used
    to run before the session existed, so it left nothing behind for an
    operator to find."""
    with pytest.raises(ValueError, match="timezone-aware"):
        backfill_groupme.backfill(since=datetime(2025, 9, 1))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert "timezone-aware" in meta.message
    assert meta.last_success_at is None


def test_a_third_party_runtime_error_is_not_logged_verbatim(job_db, monkeypatch):
    """The `except RuntimeError` branch used to log str(exc) on the grounds
    that the only RuntimeErrors reaching it were our own credential messages.
    Those are ConfigurationErrors now; what is left is requests and psycopg,
    which put URLs and connection strings in their messages."""
    def boom(*a, **k):
        raise RuntimeError("connection to postgres://user:hunter2@host failed")

    monkeypatch.setattr(backfill_groupme, "iter_messages", boom)
    with pytest.raises(RuntimeError):
        backfill_groupme.backfill(since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    meta = job_db.query(JobMeta).filter_by(
        job_name=backfill_groupme.BACKFILL_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert "hunter2" not in meta.message
    assert "RuntimeError" in meta.message
