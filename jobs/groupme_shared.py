"""Plumbing both GroupMe jobs need.

The poller and the backfill differ only in where they stop and what they call
the run afterwards. Everything between - walking newest-first until a cutoff,
storing in committed batches, and naming a ceiling-truncated run honestly - was
duplicated, and the two copies had already drifted apart once (the backfill
learned to batch and to read WalkState; the poller did neither).
"""

from datetime import datetime, timezone
from typing import Callable, Iterable, Iterator, Optional

from sqlalchemy.orm import Session

from api.chat_store import upsert_messages

BATCH_SIZE = 200

# A run the page ceiling cut short is neither a success nor an error: real
# messages were stored, but the OLDEST end of the requested range is missing.
# record_job_run() only advances last_success_at on "success", so recording a
# truncated walk under this status deliberately leaves the last-known-good
# timestamp where it was - which is exactly what monitoring should see.
STATUS_INCOMPLETE = "incomplete"


def messages_until(messages: Iterable[dict],
                   cutoff: datetime) -> Iterator[dict]:
    """Yield messages until one older than `cutoff`, then STOP the walk.

    Stopping, not filtering. Both callers walk a rate-limited API newest-first,
    and the cutoff is the only stop condition besides the page ceiling, so a
    filter-but-keep-walking version would drag the entire group history through
    the API on every run.
    """
    for message in messages:
        created = datetime.fromtimestamp(message["created_at"], tz=timezone.utc)
        if created < cutoff:
            return
        yield message


def store_in_batches(db: Session, messages: Iterable[dict],
                     batch_size: int = BATCH_SIZE,
                     on_progress: Optional[Callable[[int, int], None]] = None
                     ) -> tuple[int, int]:
    """Upsert `messages` in committed batches. Returns (inserted, updated).

    Each full batch commits as it completes, so a failure partway through a
    long walk keeps the work already done rather than discarding the whole run.

    The trailing partial batch is deliberately left PENDING for the caller to
    commit. Both jobs finish by writing a job_meta row, and record_job_run()
    commits, so the last rows and the run's own bookkeeping land in one
    transaction instead of two adjacent ones with nothing between them.

    On any error the caller must roll back before recording the failure. That
    discards only the pending partial batch; committed batches stand.

    Args:
        on_progress: called with the running (inserted, updated) totals after
            each committed batch, for jobs long enough to want a heartbeat.
    """
    inserted = 0
    updated = 0
    batch: list[dict] = []

    for message in messages:
        batch.append(message)
        if len(batch) >= batch_size:
            new, refreshed = upsert_messages(db, batch)
            db.commit()
            inserted += new
            updated += refreshed
            batch = []
            if on_progress:
                on_progress(inserted, updated)

    if batch:
        # Left uncommitted on purpose - see the docstring.
        new, refreshed = upsert_messages(db, batch)
        inserted += new
        updated += refreshed

    return inserted, updated


def is_lock_contention(exc: BaseException) -> bool:
    """Whether a RuntimeError is advisory_lock() reporting a busy lock.

    A busy lock is normal operation - the other run is doing the work - so both
    jobs record it as "skipped" rather than an error, the same way
    jobs/sheets_ingestion_shared.py does. Matching on the message is what that
    module does; api/job_locks.py raises a bare RuntimeError, so there is no
    type to match on instead.
    """
    return isinstance(exc, RuntimeError) and "advisory lock" in str(exc)


def unexpected_error_message(exc: BaseException, activity: str) -> str:
    """A job_meta message for an exception that is not known to be safe.

    str(exc) on an arbitrary exception can carry a token or a raw response body
    into job_meta and the Railway logs - a KeyError from a changed GroupMe
    envelope is raised with the missing key, and a requests error quotes the
    URL. Record the exception TYPE only; redaction of GroupMe's own errors
    belongs in api/groupme.py, and the re-raise keeps the full traceback in the
    logs where it is not persisted.
    """
    return (f"unexpected {type(exc).__name__} during {activity} "
            f"(details withheld; see job logs)")
