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
    # autoflush=False mirrors api/database.py's SessionLocal. Production runs
    # under those flush semantics, so the tests must too: an autoflushing test
    # session silently supplies a flush that production would not, which once
    # let a load-bearing db.flush() be deleted from api/chat_store.py with the
    # whole suite still green.
    session = sessionmaker(bind=engine, autoflush=False)()
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


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    """One checked-out connection. Records what ran on it and when it closed.

    Advisory locks are per-connection, so which connection a statement lands
    on is the entire property under test - a fake that pools everything into
    one statement log could not tell a correct implementation from the broken
    one it replaced.
    """

    def __init__(self, engine, acquired: bool):
        self.engine = engine
        self._acquired = acquired
        self.statements: list[str] = []
        self.closed = False
        self.isolation_level = None

    def execution_options(self, **options):
        self.isolation_level = options.get("isolation_level")
        return self

    def execute(self, statement, params=None):
        assert not self.closed, "statement issued on a closed connection"
        self.statements.append(str(statement))
        if "pg_try_advisory_lock" in str(statement):
            return _FakeResult(self._acquired)
        return _FakeResult(True)

    def close(self):
        self.closed = True
        self.engine.checkins.append(self)


class _FakeEngine:
    class _Dialect:
        name = "postgresql"

    def __init__(self, acquired: bool):
        self.dialect = self._Dialect()
        self._acquired = acquired
        self.connections: list[_FakeConnection] = []
        self.checkins: list[_FakeConnection] = []

    def connect(self):
        connection = _FakeConnection(self, self._acquired)
        self.connections.append(connection)
        return connection


class _FakePostgresSession:
    """A session that looks like Postgres to api/job_locks.advisory_lock().

    Advisory locks do not exist on SQLite - advisory_lock() skips the whole
    mechanism there - so reaching its real raise site needs a stand-in that
    reports the postgresql dialect and answers pg_try_advisory_lock. No network
    and no database: only enough surface for that one function, plus an engine
    that hands out distinguishable connections so the lock's connection
    discipline can be asserted.
    """

    def __init__(self, acquired: bool = False):
        self.bind = _FakeEngine(acquired)
        self.statements: list[str] = []
        self.commits = 0

    @property
    def connections(self):
        """Connections advisory_lock() checked out of the engine."""
        return self.bind.connections

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return _FakeResult(True)

    def commit(self):
        """Callers commit inside the lock. That is what used to return the
        lock's connection to the pool."""
        self.commits += 1


@pytest.fixture
def postgres_session():
    """Factory: postgres_session(acquired=False) -> a busy-lock session."""
    return _FakePostgresSession
