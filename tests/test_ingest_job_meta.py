"""Sheet ingestion must report its own health.

`monitor_oauth_health.py` decides whether ingestion is alive by reading the
`job_meta` row named "ingest_sheet". Nothing ever wrote that row, so the monitor
reported a stale timestamp forever regardless of what ingestion actually did.
"""

import pytest

from api.models import JobMeta, Pick, Player
from jobs import sheets_ingestion_shared as shared
from jobs.sheets_ingestion_shared import (
    INGEST_JOB_NAME,
    ingest_players_and_picks,
    record_job_run,
)


@pytest.fixture
def persistent_db(db, monkeypatch):
    """Point ingestion at the test session and keep it open afterwards.

    `ingest_players_and_picks` closes the session it is handed, which would
    leave nothing to assert against.
    """
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(shared, "SessionLocal", lambda: db)
    return db


def _meta(session):
    return session.query(JobMeta).filter(JobMeta.job_name == INGEST_JOB_NAME).first()


# --- record_job_run ---------------------------------------------------------

def test_creates_the_row_when_absent(db):
    record_job_run(db, INGEST_JOB_NAME, "success", "did a thing")

    row = _meta(db)
    assert row is not None
    assert row.status == "success"
    assert row.message == "did a thing"
    assert row.last_run_at is not None


def test_success_stamps_last_success_at(db):
    record_job_run(db, INGEST_JOB_NAME, "success", "ok")
    assert _meta(db).last_success_at is not None


def test_failure_does_not_stamp_last_success_at(db):
    record_job_run(db, INGEST_JOB_NAME, "error", "boom")
    assert _meta(db).last_success_at is None


def test_failure_preserves_the_last_known_good_run(db):
    """A later failure must not erase when ingestion last actually worked."""
    record_job_run(db, INGEST_JOB_NAME, "success", "ok")
    good = _meta(db).last_success_at

    record_job_run(db, INGEST_JOB_NAME, "error", "boom")

    row = _meta(db)
    assert row.status == "error"
    assert row.last_success_at == good


def test_reuses_one_row_rather_than_appending(db):
    record_job_run(db, INGEST_JOB_NAME, "success", "first")
    record_job_run(db, INGEST_JOB_NAME, "success", "second")

    assert db.query(JobMeta).filter(JobMeta.job_name == INGEST_JOB_NAME).count() == 1
    assert _meta(db).message == "second"


# --- the call sites ---------------------------------------------------------

def test_successful_ingestion_is_recorded(persistent_db):
    assert ingest_players_and_picks({"Ada": {1: "BUF"}}) is True

    row = _meta(persistent_db)
    assert row.status == "success"
    assert row.last_success_at is not None
    assert "1 player" in row.message


def test_recorded_message_carries_the_counts(persistent_db):
    ingest_players_and_picks({"Ada": {1: "BUF", 2: "KC"}, "Grace": {1: "SF"}})

    message = _meta(persistent_db).message
    assert "2 players" in message
    assert "3 picks" in message


def test_failed_ingestion_is_recorded_as_error(persistent_db, monkeypatch):
    def explode(_db, _season):
        raise ValueError("database on fire")

    monkeypatch.setattr(shared, "clear_season_data", explode)

    assert ingest_players_and_picks({"Ada": {1: "BUF"}}) is False

    row = _meta(persistent_db)
    assert row.status == "error"
    assert "database on fire" in row.message
    assert row.last_success_at is None


def test_lock_contention_is_recorded_as_skipped(persistent_db, monkeypatch):
    """A busy lock is normal operation, not a failure - but still worth seeing."""
    from contextlib import contextmanager

    @contextmanager
    def busy(_db, _lock_id, **_kw):
        raise RuntimeError("Could not acquire advisory lock 1001 - another job is running.")
        yield  # pragma: no cover

    monkeypatch.setattr(shared, "advisory_lock", busy)

    assert ingest_players_and_picks({"Ada": {1: "BUF"}}) is False
    assert _meta(persistent_db).status == "skipped"


def test_reporting_failure_never_masks_a_successful_ingestion(persistent_db, monkeypatch):
    """Monitoring is not worth losing an ingestion over."""
    monkeypatch.setattr(
        shared, "record_job_run",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("job_meta table missing")),
    )

    assert ingest_players_and_picks({"Ada": {1: "BUF"}}) is True
    assert persistent_db.query(Pick).filter(Pick.season == 2026).count() == 1
