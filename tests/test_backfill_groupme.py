"""One-time walk back through GroupMe history.

The chat's membership tracks the surviving field (252 in week 1, 22 by week
14), so volume decays across the season and this is a smaller job than a
252-person chat implies. It still needs a hard page ceiling: paging backward
forever on an unexpected response shape is the failure mode that burns the
rate limit.
"""

from datetime import datetime, timezone

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

    stored = backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert stored == 1
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
        since=datetime(2025, 9, 1, tzinfo=timezone.utc)) == 0
