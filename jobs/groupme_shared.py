"""Plumbing both GroupMe jobs need.

The poller and the backfill differ only in where they stop and what they call
the run afterwards. Everything between - walking newest-first until a cutoff,
storing in committed batches, and naming a ceiling-truncated run honestly - was
duplicated, and the two copies had already drifted apart once (the backfill
learned to batch and to read WalkState; the poller did neither).
"""

import os
from datetime import datetime, timezone
from typing import Callable, Iterable, Iterator, Optional

from sqlalchemy.orm import Session

from api.chat_store import upsert_messages
from api.job_locks import is_lock_contention as _is_lock_contention
from jobs.sheets_ingestion_shared import record_job_run

BATCH_SIZE = 200

# A BACKFILL the page ceiling cut short is neither a success nor an error: real
# messages were stored, but the OLDEST end of the requested range is missing.
# record_job_run() only advances last_success_at on "success", so recording a
# truncated walk under this status deliberately leaves the last-known-good
# timestamp where it was - which is exactly what monitoring should see.
#
# This is the backfill's word and only the backfill's. The poller hitting its
# own ceiling means something much weaker - see ingest_groupme.run() - and
# borrowing this status for it froze last_success_at permanently on a job that
# was working correctly.
STATUS_INCOMPLETE = "incomplete"


class ConfigurationError(ValueError):
    """A job cannot start: a required setting is missing or malformed.

    Exists so a job can persist ``str(exc)`` for exactly this case and redact
    everything else. The messages are built here from literals and the NAME of
    an environment variable - never its value - which makes this the one
    exception on the GroupMe path whose text is safe to write to job_meta and
    the Railway logs.

    Subclasses ValueError rather than RuntimeError: the backfill's naive-`since`
    check is this same condition arriving as a bad argument.
    """


def require_credentials() -> tuple[str, str]:
    """Read the GroupMe credentials from the environment.

    Raises ConfigurationError naming the variable that is missing. It never
    names the value - a rotated or truncated token must not be echoed anywhere,
    least of all into a job_meta row an operator will paste into a chat window.
    """
    token = os.getenv("GROUPME_ACCESS_TOKEN")
    group_id = os.getenv("GROUPME_READ_GROUP_ID")
    if not token:
        raise ConfigurationError("GROUPME_ACCESS_TOKEN is not set")
    if not group_id:
        raise ConfigurationError("GROUPME_READ_GROUP_ID is not set")
    return token, group_id


def report(db: Session, job_name: str, status: str, message: str) -> None:
    """Record an outcome without ever replacing it.

    Every caller is inside an exception handler, where a bare record_job_run()
    that itself fails - a dead connection is the obvious way - raises over the
    real exception and leaves nothing recorded at all. Monitoring is not worth
    losing the traceback for. The same helper, and the same reasoning, as
    ``_report`` in jobs/sheets_ingestion_shared.py.
    """
    try:
        record_job_run(db, job_name, status, message)
    except Exception as exc:   # noqa: BLE001 - see the docstring
        print(f"⚠️ Could not record job_meta ({status}): {exc}")


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
    """Upsert `messages` in committed batches. Returns (inserted, matched).

    `matched` is rows the walk saw again and re-wrote, NOT rows whose content
    differed - upsert_messages() cannot tell those apart and does not try. A
    re-scan that changed nothing still counts every row it touched, so report
    it as re-seen rather than as refreshed.

    Each full batch commits as it completes, so a failure partway through a
    long walk keeps the work already done rather than discarding the whole run.

    The trailing partial batch is deliberately left PENDING for the caller to
    commit. Both jobs finish by writing a job_meta row, and record_job_run()
    commits, so the last rows and the run's own bookkeeping land in one
    transaction instead of two adjacent ones with nothing between them.

    On any error the caller must roll back before recording the failure. That
    discards only the pending partial batch; committed batches stand.

    Args:
        on_progress: called with the running (inserted, matched) totals after
            each committed batch, for jobs long enough to want a heartbeat.
    """
    inserted = 0
    matched = 0
    batch: list[dict] = []

    for message in messages:
        batch.append(message)
        if len(batch) >= batch_size:
            new, seen_again = upsert_messages(db, batch)
            db.commit()
            inserted += new
            matched += seen_again
            batch = []
            if on_progress:
                on_progress(inserted, matched)

    if batch:
        # Left uncommitted on purpose - see the docstring.
        new, seen_again = upsert_messages(db, batch)
        inserted += new
        matched += seen_again

    return inserted, matched


def is_lock_contention(exc: BaseException) -> bool:
    """Whether an exception is advisory_lock() reporting a busy lock.

    A busy lock is normal operation - the other run is doing the work - so both
    jobs record it as "skipped" rather than an error, the same way
    jobs/sheets_ingestion_shared.py does.

    Re-exported from api/job_locks.py, which now raises LockContentionError.
    This used to match "advisory lock" in the message, and the test that
    claimed to pin that message hand-wrote its own copy of it - so rewording
    the raise site left the suite green while both jobs began recording routine
    contention as an error. The raiser and the detector now share a type.
    """
    return _is_lock_contention(exc)


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
