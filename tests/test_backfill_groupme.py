"""One-time walk back through GroupMe history.

The chat's membership tracks the surviving field (252 in week 1, 22 by week
14), so volume decays across the season and this is a smaller job than a
252-person chat implies. It still needs a hard page ceiling: paging backward
forever on an unexpected response shape is the failure mode that burns the
rate limit.
"""

from datetime import datetime, timezone

from api.models import ChatMessage
from jobs import backfill_groupme


def raw(mid, created):
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": [], "created_at": created}


SEP_2025 = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp())
AUG_2025 = int(datetime(2025, 8, 1, tzinfo=timezone.utc).timestamp())


def test_backfill_stops_at_the_since_date(job_db, monkeypatch):
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m2", SEP_2025), raw("m1", AUG_2025)]))

    stored = backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert stored == 1
    assert [r.message_id for r in job_db.query(ChatMessage).all()] == ["m2"]


def test_backfill_returns_zero_on_empty_history(job_db, monkeypatch):
    monkeypatch.setattr(backfill_groupme, "iter_messages", lambda *a, **k: iter([]))
    assert backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc)) == 0
