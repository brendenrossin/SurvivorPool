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
    assert any("pg_try_advisory_lock" in s for s in db.statements)
    assert any("pg_advisory_unlock" in s for s in db.statements)


def test_sqlite_skips_locking_rather_than_failing(db):
    """Dev and the test suite run on SQLite, which has no advisory locks."""
    db.execute(text("SELECT 1"))
    with advisory_lock(db, LOCK_GROUPME_INGESTION):
        pass
