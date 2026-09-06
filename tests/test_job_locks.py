"""Advisory locks are how the jobs avoid writing over each other.

Every one of them treats a busy lock as a routine skip rather than a failure,
so how contention is *recognised* decides whether a normal Sunday afternoon
shows up in monitoring as an error. These tests provoke the real error from
``advisory_lock`` rather than hand-writing a copy of its message: a copy proves
nothing, and the copy that used to live in tests/test_groupme_shared.py let a
rename at the raise site pass the whole suite.
"""

import pytest
from sqlalchemy import text

from api.job_locks import (LOCK_GROUPME_INGESTION, LockContentionError,
                           advisory_lock, is_lock_contention)


def provoke_contention(session_factory) -> LockContentionError:
    """The exception advisory_lock() actually raises when the lock is held."""
    db = session_factory(acquired=False)
    with pytest.raises(LockContentionError) as caught:
        with advisory_lock(db, LOCK_GROUPME_INGESTION):
            pytest.fail("the body must not run when the lock is busy")
    return caught.value


def test_a_busy_lock_raises_the_contention_type(postgres_session):
    """The type is what callers should key off - it survives rewording."""
    assert is_lock_contention(provoke_contention(postgres_session))


def test_the_contention_error_is_still_a_runtime_error(postgres_session):
    """jobs/sheets_ingestion_shared.py and jobs/update_scores.py both catch
    RuntimeError around the lock. Narrowing the base class would turn their
    routine skip into an uncaught crash."""
    assert isinstance(provoke_contention(postgres_session), RuntimeError)


def test_the_contention_message_keeps_the_substring_two_jobs_match_on(
        postgres_session):
    """jobs/sheets_ingestion_shared.py and jobs/update_scores.py still detect
    contention with `"advisory lock" in str(e)`.

    Nothing enforced that coupling before: rewording the raise site left the
    entire suite green while both jobs silently began recording a busy lock as
    an error. This is the pin. When those two switch to is_lock_contention(),
    delete this test - not the message.
    """
    assert "advisory lock" in str(provoke_contention(postgres_session))


def test_an_unrelated_runtime_error_is_not_contention():
    """A lookalike message is not contention. Only the type is."""
    assert not is_lock_contention(RuntimeError("advisory lock"))
    assert not is_lock_contention(ValueError("GROUPME_ACCESS_TOKEN is not set"))


def test_an_acquired_lock_runs_the_body_and_releases(postgres_session):
    db = postgres_session(acquired=True)
    ran = []
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        ran.append(True)

    assert ran == [True]
    statements = db.connections[0].statements
    assert any("pg_try_advisory_lock" in s for s in statements)
    assert any("pg_advisory_unlock" in s for s in statements)


# --- connection discipline --------------------------------------------------
#
# pg_try_advisory_lock is session-scoped: the lock belongs to the DBAPI
# connection that took it. Callers commit inside the lock - store_in_batches
# commits once per batch - and a commit returns the session's connection to
# the pool. api/database.py's engine takes no pool arguments, so that pool is
# the default QueuePool of five, not one connection. A single-threaded job
# usually gets the same connection back, which is why riding on the session
# worked; it was luck. These pin the invariant instead: the connection that
# acquires the lock is the connection that releases it, and it is not returned
# to the pool in between.
#
# None of this executes on SQLite, where the suite runs, so these assert
# against a fake engine rather than a real Postgres one. What they can prove is
# the calling discipline. What they cannot prove is that Postgres honours it -
# only a real Postgres can.

def test_the_lock_does_not_ride_on_the_callers_session(postgres_session):
    """The session's connection goes back to the pool on every commit."""
    db = postgres_session(acquired=True)
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        pass

    assert db.statements == [], (
        f"lock statements were issued on the caller's session: {db.statements}")


def test_lock_and_unlock_run_on_the_same_connection(postgres_session):
    """An unlock from a different connection silently does nothing: Postgres
    returns false and the lock stays held by whoever took it."""
    db = postgres_session(acquired=True)
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        pass

    assert len(db.connections) == 1
    statements = db.connections[0].statements
    assert [s for s in statements if "advisory" in s] == [
        "SELECT pg_try_advisory_lock(:lock_id)",
        "SELECT pg_advisory_unlock(:lock_id)",
    ]


def test_committing_inside_the_lock_does_not_move_it(postgres_session):
    """store_in_batches commits once per batch. That is the exact thing that
    used to hand the lock's connection back to the pool mid-run."""
    db = postgres_session(acquired=True)
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        db.commit()
        assert not db.connections[0].closed, "a commit closed the lock connection"
        db.commit()
        db.commit()

    assert db.commits == 3
    assert len(db.connections) == 1, "the lock changed connections mid-run"
    # The unlock still landed on the connection that took the lock, after
    # three commits that would have moved a session-borne lock.
    assert db.connections[0].statements[-1] == "SELECT pg_advisory_unlock(:lock_id)"


def test_the_lock_connection_is_held_open_until_after_the_unlock(postgres_session):
    """Returned to the pool early, the lock would be strandable on it."""
    db = postgres_session(acquired=True)
    connection = None
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        connection = db.connections[0]
        assert not connection.closed, "lock connection returned to the pool mid-run"

    assert connection.closed, "lock connection was never released back to the pool"


def test_a_busy_lock_releases_the_connection_without_unlocking(postgres_session):
    """Unlocking a lock this process never took asks Postgres to drop somebody
    else's lock. It returns false and logs, for what is a routine skip."""
    db = postgres_session(acquired=False)
    with pytest.raises(LockContentionError):
        with advisory_lock(db, LOCK_GROUPME_INGESTION):
            pytest.fail("the body must not run when the lock is busy")

    connection = db.connections[0]
    assert not any("pg_advisory_unlock" in s for s in connection.statements)
    assert connection.closed, "the connection leaked on the contention path"


def test_the_connection_is_released_even_when_the_body_raises(postgres_session):
    db = postgres_session(acquired=True)
    with pytest.raises(ValueError):
        with advisory_lock(db, LOCK_GROUPME_INGESTION):
            raise ValueError("job blew up")

    connection = db.connections[0]
    assert any("pg_advisory_unlock" in s for s in connection.statements)
    assert connection.closed


def test_the_lock_connection_does_not_sit_idle_in_transaction(postgres_session):
    """It is held for the whole job. In a transaction that whole time it would
    hold back vacuum for no benefit - session advisory locks do not care about
    transaction state."""
    db = postgres_session(acquired=True)
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        pass

    assert db.connections[0].isolation_level == "AUTOCOMMIT"


def test_the_engine_api_the_lock_depends_on_is_real(db):
    """Everything above this line talks to a fake engine.

    A fake proves the calling discipline and nothing about whether the calls
    exist. This runs the exact chain advisory_lock() uses -
    engine.connect().execution_options(isolation_level=...) -> execute ->
    close - against a real SQLAlchemy engine, so the fake cannot quietly drift
    into modelling an API SQLAlchemy does not have.

    Real Postgres is still the only thing that can prove the lock semantics.
    """
    connection = db.bind.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        assert connection.execute(text("SELECT 1")).scalar() == 1
    finally:
        connection.close()

    assert connection.closed


def test_sqlite_skips_locking_rather_than_failing(db):
    """Dev and the test suite run on SQLite, which has no advisory locks."""
    db.execute(text("SELECT 1"))
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        pass
