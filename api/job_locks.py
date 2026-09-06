#!/usr/bin/env python3
"""
PostgreSQL Advisory Locks for Job Coordination

Prevents race conditions between sheet ingestion and score updates.
"""

from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session


# Lock IDs for different job types
LOCK_INGESTION_AND_SCORING = 1001  # Shared lock for both ingestion and score updates

# Shared by the GroupMe poller and the GroupMe backfill, which write the same
# chat_messages rows: a Railway retry overlapping the run it retried, or a
# manual backfill overlapping the poller's cron, would otherwise miss each
# other's uncommitted rows and collide on the message_id primary key mid-batch.
# Deliberately NOT 1001 - GroupMe touches none of picks/pick_results, and
# sharing that lock would make chat ingestion block score updates for nothing.
LOCK_GROUPME_INGESTION = 1002


class LockContentionError(RuntimeError):
    """Another job holds the lock. Normal operation, not a failure.

    Subclasses RuntimeError deliberately: jobs/sheets_ingestion_shared.py and
    jobs/update_scores.py both catch RuntimeError and then match "advisory
    lock" in the message, so raising this instead of a bare RuntimeError
    changes nothing for them while giving new callers something to match on
    that a reworded message cannot silently break.

    New code should use is_lock_contention() rather than either the type or the
    string.
    """


def is_lock_contention(exc: BaseException) -> bool:
    """Whether `exc` is advisory_lock() reporting a lock somebody else holds.

    Matching on the type, not on the message. The message match this replaced
    was a copy of a string with nothing enforcing the copy - renaming the text
    at the raise site left every test green and turned a routine skip into a
    recorded error.
    """
    return isinstance(exc, LockContentionError)


@contextmanager
def advisory_lock(db: Session, lock_id: int, timeout_seconds: int = 300):
    """
    Acquire a PostgreSQL advisory lock for the duration of the context.

    This ensures only ONE job can modify picks/pick_results at a time,
    preventing race conditions between sheet ingestion and score updates.

    The lock is taken on its own connection, checked out from the engine for
    the whole lifetime of the context and closed afterwards. It deliberately
    does NOT ride on `db`.

    ``pg_try_advisory_lock`` is session-scoped: the lock belongs to the DBAPI
    connection that took it, and only that connection can release it. `db`
    cannot offer that guarantee, because callers commit inside this block -
    jobs/groupme_shared.store_in_batches commits once per batch - and a commit
    returns the connection to the pool. api/database.py creates the engine with
    no pool arguments, so that is SQLAlchemy's default QueuePool holding five
    connections, not one. A single-threaded job checking back out of an idle
    pool will usually get the same connection, which is why this worked; it was
    luck, not mutual exclusion. Land a later batch on a different connection and
    two jobs run concurrently while believing they hold the lock, and the
    unlock returns false, stranding the lock on the original connection until
    the pool recycles it - after which every run records "skipped" forever.

    A dedicated connection makes the invariant structural: the connection that
    acquires the lock is the connection that releases it, and it is never
    returned to the pool in between.

    Runs in AUTOCOMMIT so the lock connection does not sit `idle in
    transaction` for the length of a job, which would hold back vacuum. Session
    advisory locks are independent of transaction state, so this costs nothing.

    Args:
        db: SQLAlchemy session. Used only to find the engine - no lock
            statement is issued on it.
        lock_id: Unique integer identifier for this lock
        timeout_seconds: Accepted for backwards compatibility. Unused:
            pg_try_advisory_lock does not wait, it reports and returns.

    Raises:
        LockContentionError: If another session already holds the lock. It is a
            RuntimeError, so pre-existing ``except RuntimeError`` handlers are
            unaffected.
    """
    engine = db.bind

    # SQLite has no advisory locks. Documented no-op: dev and the whole test
    # suite run there, and single-process dev has nothing to race with.
    engine_name = engine.dialect.name
    if engine_name == "sqlite":
        print("⚠️  SQLite detected - skipping advisory lock (dev mode)")
        yield
        return

    print(f"🔒 Attempting to acquire advisory lock {lock_id}...")

    lock_connection = engine.connect().execution_options(
        isolation_level="AUTOCOMMIT")
    try:
        # pg_try_advisory_lock returns True if lock acquired, False otherwise
        acquired = lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id}
        ).scalar()

        if not acquired:
            # The words "advisory lock" are load-bearing until
            # jobs/sheets_ingestion_shared.py and jobs/update_scores.py stop
            # matching on them; tests/test_job_locks.py pins that substring
            # against the real raise so rewording it here fails loudly.
            raise LockContentionError(
                f"Could not acquire advisory lock {lock_id} - another job is running. "
                f"Will retry on next cron schedule."
            )

        print(f"✅ Advisory lock {lock_id} acquired")

        try:
            yield
        finally:
            # Only unlocks a lock this call actually took. The unconditional
            # release this replaced also fired on the contention path, asking
            # Postgres to drop a lock held by somebody else and logging a
            # warning for a routine skip.
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id}
            )
            print(f"🔓 Advisory lock {lock_id} released")
    finally:
        lock_connection.close()
