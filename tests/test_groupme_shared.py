"""The plumbing both GroupMe jobs share.

Batching is the reason a long walk that dies partway through keeps the work it
already did, and the pending-trailing-batch contract is what lets a job's rows
and its job_meta row commit together. Both are subtle enough to test directly
rather than only through the jobs.
"""

from datetime import datetime, timedelta, timezone

import pytest

from api import job_locks
from api.models import ChatMessage
from jobs import groupme_shared


def raw(mid, created=None):
    if created is None:
        created = int(datetime.now(timezone.utc).timestamp())
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": [], "created_at": created}


def test_messages_until_stops_the_walk_rather_than_filtering(db):
    """Filtering would drag the whole group history through a rate-limited API
    on every run; the cutoff is one of only two stop conditions."""
    now = datetime.now(timezone.utc)
    old = int((now - timedelta(days=30)).timestamp())
    consumed = []

    def walking():
        for message in [raw("a"), raw("b", created=old), raw("c")]:
            consumed.append(message["id"])
            yield message

    kept = list(groupme_shared.messages_until(walking(), now - timedelta(days=14)))

    assert [m["id"] for m in kept] == ["a"]
    assert consumed == ["a", "b"]


def test_full_batches_commit_as_they_complete(db):
    """A failure later in the walk must not discard work already done."""
    def walking():
        yield raw("m1")
        yield raw("m2")
        yield raw("m3")
        raise KeyError("envelope changed")

    with pytest.raises(KeyError):
        groupme_shared.store_in_batches(db, walking(), batch_size=2)

    db.rollback()
    assert sorted(r.message_id for r in db.query(ChatMessage).all()) == ["m1", "m2"]


def test_the_trailing_partial_batch_is_left_for_the_caller_to_commit(db):
    """Deliberate: the caller's record_job_run() commits, so the last rows and
    the run's own bookkeeping land in one transaction instead of two."""
    inserted, updated = groupme_shared.store_in_batches(
        db, iter([raw("m1")]), batch_size=200)

    assert (inserted, updated) == (1, 0)
    db.rollback()
    assert db.query(ChatMessage).count() == 0


def test_progress_is_reported_with_running_totals(db):
    seen = []
    groupme_shared.store_in_batches(
        db, iter([raw("m1"), raw("m2"), raw("m3"), raw("m4")]),
        batch_size=2, on_progress=lambda i, u: seen.append((i, u)))

    assert seen == [(2, 0), (4, 0)]


def test_counts_separate_new_rows_from_re_seen_ones(db):
    """The second number is rows matched, not rows whose content changed -
    upsert_messages() re-writes every field it touches either way."""
    groupme_shared.store_in_batches(db, iter([raw("m1")]))
    db.commit()

    assert groupme_shared.store_in_batches(
        db, iter([raw("m1"), raw("m2")])) == (1, 1)


def test_lock_contention_is_recognised_from_the_real_raise(postgres_session):
    """Provoked from api/job_locks.py, never hand-written.

    The version this replaces built its own copy of the contention message and
    asserted the detector matched the copy. It pinned nothing: rewording the
    real message left the whole suite green while both GroupMe jobs began
    recording a routine busy lock as an error. Reach the actual raise site
    instead - tests/test_job_locks.py covers the rest of that contract.
    """
    busy = postgres_session(acquired=False)
    with pytest.raises(job_locks.LockContentionError) as caught:
        with job_locks.advisory_lock(busy, job_locks.LOCK_GROUPME_INGESTION):
            pytest.fail("the body must not run when the lock is busy")

    assert groupme_shared.is_lock_contention(caught.value)
    assert not groupme_shared.is_lock_contention(
        groupme_shared.ConfigurationError("GROUPME_ACCESS_TOKEN is not set"))
    # A lookalike message is not contention; only the type is.
    assert not groupme_shared.is_lock_contention(RuntimeError("advisory lock"))


def test_missing_credentials_names_the_variable_and_never_its_value(monkeypatch):
    """This message is the one exception text the jobs persist verbatim."""
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "super-secret-token-value")
    monkeypatch.setenv("GROUPME_READ_GROUP_ID", "g1")
    assert groupme_shared.require_credentials() == ("super-secret-token-value", "g1")

    monkeypatch.delenv("GROUPME_ACCESS_TOKEN")
    with pytest.raises(groupme_shared.ConfigurationError) as caught:
        groupme_shared.require_credentials()

    assert "GROUPME_ACCESS_TOKEN" in str(caught.value)
    assert "super-secret-token-value" not in str(caught.value)


def test_report_swallows_a_job_meta_failure_rather_than_masking_the_real_one(
        db, monkeypatch, capsys):
    """Every caller is inside an exception handler. A record_job_run() that
    itself raises there would replace the real exception and record nothing -
    the reason jobs/sheets_ingestion_shared.py wraps it the same way."""
    def boom(*a, **k):
        raise RuntimeError("job_meta table missing")

    monkeypatch.setattr(groupme_shared, "record_job_run", boom)
    groupme_shared.report(db, "ingest_groupme", "error", "something failed")

    assert "Could not record job_meta (error)" in capsys.readouterr().out


def test_an_unexpected_error_is_summarised_without_its_payload():
    """str(exc) on an arbitrary exception can carry a token or a raw response
    body into job_meta and Railway's hosted logs."""
    message = groupme_shared.unexpected_error_message(
        KeyError("super-secret-token-value"), "GroupMe ingestion")

    assert "KeyError" in message
    assert "GroupMe ingestion" in message
    assert "super-secret-token-value" not in message
