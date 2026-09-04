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


@contextmanager
def advisory_lock(db: Session, lock_id: int, timeout_seconds: int = 300):
    """
    Acquire a PostgreSQL advisory lock for the duration of the context.

    This ensures only ONE job can modify picks/pick_results at a time,
    preventing race conditions between sheet ingestion and score updates.

    Args:
        db: SQLAlchemy session
        lock_id: Unique integer identifier for this lock
        timeout_seconds: Max time to wait for lock (default 5 minutes)

    Raises:
        RuntimeError: If lock cannot be acquired within timeout
    """
    # Check if we're using SQLite (which doesn't support advisory locks)
    engine_name = db.bind.dialect.name
    if engine_name == "sqlite":
        # SQLite doesn't support advisory locks, just skip locking
        print("⚠️  SQLite detected - skipping advisory lock (dev mode)")
        yield
        return

    print(f"🔒 Attempting to acquire advisory lock {lock_id}...")

    try:
        # Try to acquire lock with timeout
        # pg_try_advisory_lock returns True if lock acquired, False otherwise
        result = db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id}
        ).scalar()

        if not result:
            raise RuntimeError(
                f"Could not acquire advisory lock {lock_id} - another job is running. "
                f"Will retry on next cron schedule."
            )

        print(f"✅ Advisory lock {lock_id} acquired")

        yield

    finally:
        # Always release the lock
        if engine_name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": lock_id}
            )
            print(f"🔓 Advisory lock {lock_id} released")
