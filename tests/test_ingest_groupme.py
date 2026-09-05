"""The GroupMe poller re-scans a trailing window.

Favorite counts rise after a message posts, so a poller that fetches only
messages newer than its high-water mark freezes every count at whatever it was
seconds after posting. It re-reads a trailing window instead and lets the
upsert refresh what changed.
"""

from datetime import datetime, timezone

import pytest

from api.models import ChatMessage, JobMeta
from jobs import ingest_groupme


@pytest.fixture
def job_db(db, monkeypatch):
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ingest_groupme, "SessionLocal", lambda: db)
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("GROUPME_READ_GROUP_ID", "g1")
    return db


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


def test_missing_credentials_is_a_clear_error(job_db, monkeypatch):
    monkeypatch.delenv("GROUPME_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GROUPME_ACCESS_TOKEN"):
        ingest_groupme.run()
