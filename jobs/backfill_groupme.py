"""One-time walk back through GroupMe history to the season start.

Run once per season, not on a cron. The poller in ingest_groupme.py keeps
things current afterwards.
"""

from datetime import datetime, timezone
from typing import Optional

from api.database import SessionLocal
from api.groupme import GroupMeError, WalkState, iter_messages
from api.job_locks import LOCK_GROUPME_INGESTION, advisory_lock
from jobs.groupme_shared import (BATCH_SIZE, STATUS_INCOMPLETE,
                                 ConfigurationError, is_lock_contention,
                                 messages_until, report, require_credentials,
                                 store_in_batches, unexpected_error_message)

BACKFILL_GROUPME_JOB_NAME = "backfill_groupme"
MAX_PAGES = 500          # 50k messages; a ceiling, not an expectation


def _parse_since(value: str) -> datetime:
    """Parse a --since timestamp into UTC.

    `.replace(tzinfo=utc)` relabels rather than converts, so an offset-bearing
    timestamp such as 2025-09-01T00:00:00-07:00 silently became midnight UTC -
    seven hours of history quietly outside the range. Convert when the value
    carries an offset; attach UTC only when it is naive (a bare date, which is
    what the default is).
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def backfill(since: datetime,
             max_pages: int = MAX_PAGES) -> Optional[tuple[int, int]]:
    """Store every message posted on or after `since`.

    Returns (inserted, matched), not their sum. On a re-run over overlapping
    history the sum is dominated by re-touched rows, so a single number cannot
    tell an operator progress from re-scan noise. `matched` counts rows the
    walk saw again, not rows whose content changed - see store_in_batches().

    Returns None when the backfill DID NOT RUN because another GroupMe job
    holds the lock. (0, 0) means it ran and found nothing; the two are worth
    telling apart for a job an operator invokes by hand and waits on.
    """
    # The session is opened before the argument check and before the
    # credentials are read. Both used to raise out here with no session open
    # and no job_meta row - a revoked GROUPME_ACCESS_TOKEN left exactly as
    # little trace as an unhandled envelope change once did.
    db = SessionLocal()
    try:
        walk = WalkState()

        def progress(inserted, matched):
            print(f"  ... {inserted} new, {matched} re-seen")

        try:
            if since.tzinfo is None or since.utcoffset() is None:
                # Comparing naive to aware raises TypeError, and it would raise
                # inside the walk - after batches had already committed, leaving
                # a partial backfill behind a traceback. Fail before the first
                # request instead.
                raise ConfigurationError(
                    "backfill(since=...) requires a timezone-aware datetime")

            token, group_id = require_credentials()

            # Same lock as the poller: this walks and writes the very rows the
            # poller's trailing window is re-scanning, and an operator running
            # this by hand has no idea when the cron next fires.
            with advisory_lock(db, LOCK_GROUPME_INGESTION):
                inserted, matched = store_in_batches(
                    db,
                    messages_until(
                        iter_messages(group_id, token, max_pages=max_pages,
                                      walk=walk),
                        since),
                    batch_size=BATCH_SIZE,
                    on_progress=progress)

                if walk.stopped_at_ceiling:
                    # Not a success, and unlike the poller's ceiling this really
                    # does mean history is missing. The walk goes newest-first,
                    # so what is absent is the OLDEST end of the range - the
                    # early-season history the corpus most wants, back when the
                    # group had 252 members rather than 22.
                    print(f"⚠️ Backfill INCOMPLETE: stopped at the {max_pages}-page "
                          f"ceiling after {inserted} new / {matched} re-seen, "
                          f"before reaching {since.date()}. The missing history is "
                          f"the oldest part of the range. Re-run with a larger "
                          f"--max-pages, or with a later --since and then work "
                          f"backward from there.")
                    report(
                        db, BACKFILL_GROUPME_JOB_NAME, STATUS_INCOMPLETE,
                        f"{inserted} new, {matched} re-seen; stopped at the "
                        f"{max_pages}-page ceiling before reaching {since.date()}")
                    return inserted, matched

                # record_job_run() commits, which is also what commits the
                # trailing partial batch store_in_batches() left pending.
                report(
                    db, BACKFILL_GROUPME_JOB_NAME, "success",
                    f"{inserted} new, {matched} re-seen since {since.date()}")
        except ConfigurationError as exc:
            # The one exception whose text is safe to persist: built in
            # jobs/groupme_shared.py from literals and an environment variable
            # NAME, never its value.
            db.rollback()
            report(db, BACKFILL_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except GroupMeError as exc:
            # Already redacted at its raise site in api/groupme.py.
            db.rollback()
            report(db, BACKFILL_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except RuntimeError as exc:
            db.rollback()
            if is_lock_contention(exc):
                # Normal operation: the poller is mid-run, or another backfill
                # is. But this is a one-shot an operator started and is waiting
                # on, so "will retry next run" - true for the poller's cron - is
                # a lie here. Nothing was backfilled and nothing will be until
                # somebody runs it again.
                print(f"⏭️  GroupMe backfill DID NOT RUN (lock busy): {exc}")
                report(db, BACKFILL_GROUPME_JOB_NAME, "skipped",
                       "Lock busy: the backfill did not run. Re-run it once "
                       "the other GroupMe job finishes.")
                return None
            # Somebody else's RuntimeError - requests and psycopg raise them
            # with a URL or a connection string in the message. The comment that
            # used to justify logging str(exc) here named the credential checks,
            # which are ConfigurationErrors now.
            report(db, BACKFILL_GROUPME_JOB_NAME, "error",
                   unexpected_error_message(exc, "GroupMe backfill"))
            raise
        except Exception as exc:
            # A KeyError from a changed GroupMe envelope is the realistic case.
            # Uncaught, it crashed the walk with a raw traceback and left no
            # record of how far the backfill got. The rollback drops only the
            # pending partial batch; committed batches stand. Type name only -
            # str(exc) on an arbitrary exception can carry a token or a raw
            # response body into job_meta. The re-raise keeps it loud.
            db.rollback()
            report(db, BACKFILL_GROUPME_JOB_NAME, "error",
                   unexpected_error_message(exc, "GroupMe backfill"))
            raise

        print(f"✅ Backfilled {inserted} new, {matched} re-seen "
              f"since {since.date()}")
        return inserted, matched
    finally:
        try:
            db.close()
        except Exception:
            pass


def main(argv=None) -> int:
    """Exit code for the one-shot: 0 if the backfill ran, 1 if it did not.

    `python jobs/backfill_groupme.py && echo done` used to print `done` after a
    run that never happened, because a busy lock returned quietly and __main__
    threw the return value away.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Backfill GroupMe history")
    parser.add_argument("--since", default="2025-09-01",
                        help="ISO date to walk back to (default: 2025 season "
                             "start). Naive values are read as UTC; an offset "
                             "is converted, not relabelled.")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args(argv)

    result = backfill(since=_parse_since(args.since), max_pages=args.max_pages)
    return 0 if result is not None else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
