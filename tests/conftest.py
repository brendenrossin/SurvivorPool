"""Shared pytest fixtures.

Tests run against an in-memory SQLite database with foreign key enforcement
enabled, so FK violations surface here the same way they would on Postgres.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.models import Base, Player, Pick


@pytest.fixture
def db():
    """In-memory SQLite session with the real schema and FKs enforced."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def job_db(db, monkeypatch):
    """A session the jobs will not close, with GroupMe credentials stubbed."""
    from jobs import backfill_groupme, ingest_groupme

    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ingest_groupme, "SessionLocal", lambda: db)
    monkeypatch.setattr(backfill_groupme, "SessionLocal", lambda: db)
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("GROUPME_READ_GROUP_ID", "g1")
    return db


@pytest.fixture
def seeded_db(db):
    """Two seasons of history: a 2025-only player and a two-season player."""
    alumni = Player(display_name="Alumni Only 2025")
    returning = Player(display_name="Returning Player")
    db.add_all([alumni, returning])
    db.flush()

    db.add_all([
        Pick(player_id=alumni.player_id, season=2025, week=1, team_abbr="BUF"),
        Pick(player_id=alumni.player_id, season=2025, week=2, team_abbr="KC"),
        Pick(player_id=returning.player_id, season=2025, week=1, team_abbr="DAL"),
        Pick(player_id=returning.player_id, season=2026, week=1, team_abbr="SF"),
    ])
    db.commit()
    return db
