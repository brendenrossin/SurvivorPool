"""The plumbing both GroupMe jobs share.

Batching is the reason a long walk that dies partway through keeps the work it
already did, and the pending-trailing-batch contract is what lets a job's rows
and its job_meta row commit together. Both are subtle enough to test directly
rather than only through the jobs.
"""

from datetime import datetime, timedelta, timezone

import pytest

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


def test_counts_separate_new_rows_from_refreshed_ones(db):
    groupme_shared.store_in_batches(db, iter([raw("m1")]))
    db.commit()

    assert groupme_shared.store_in_batches(
        db, iter([raw("m1"), raw("m2")])) == (1, 1)


def test_lock_contention_is_recognised_by_its_message():
    """api/job_locks.py raises a bare RuntimeError, so there is no exception
    type to match on - the same string check jobs/sheets_ingestion_shared.py
    uses. If that message ever changes, a busy lock starts being recorded as an
    error, which is what this pins."""
    busy = RuntimeError("Could not acquire advisory lock 1002 - another job is "
                        "running. Will retry on next cron schedule.")
    assert groupme_shared.is_lock_contention(busy)
    assert not groupme_shared.is_lock_contention(
        RuntimeError("GROUPME_ACCESS_TOKEN is not set"))
    assert not groupme_shared.is_lock_contention(KeyError("advisory lock"))


def test_an_unexpected_error_is_summarised_without_its_payload():
    """str(exc) on an arbitrary exception can carry a token or a raw response
    body into job_meta and Railway's hosted logs."""
    message = groupme_shared.unexpected_error_message(
        KeyError("super-secret-token-value"), "GroupMe ingestion")

    assert "KeyError" in message
    assert "GroupMe ingestion" in message
    assert "super-secret-token-value" not in message
