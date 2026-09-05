"""One-time walk back through GroupMe history to the season start.

Run once per season, not on a cron. The poller in ingest_groupme.py keeps
things current afterwards.
"""

import os
from datetime import datetime, timezone

from api.database import SessionLocal
from api.groupme import GroupMeError, WalkState, iter_messages
from api.job_locks import LOCK_GROUPME_INGESTION, advisory_lock
from jobs.groupme_shared import (BATCH_SIZE, STATUS_INCOMPLETE,
                                 is_lock_contention, messages_until,
                                 store_in_batches, unexpected_error_message)
from jobs.sheets_ingestion_shared import record_job_run

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


def backfill(since: datetime, max_pages: int = MAX_PAGES) -> tuple[int, int]:
    """Store every message posted on or after `since`.

    Returns (inserted, updated), not their sum. On a re-run over overlapping
    history the sum is dominated by re-touched rows, so a single number cannot
    tell an operator progress from re-scan noise.
    """
    if since.tzinfo is None or since.utcoffset() is None:
        # Comparing naive to aware raises TypeError, and it would raise inside
        # the walk - after batches had already committed, leaving a partial
        # backfill behind a traceback. Fail before the first request instead.
        raise ValueError(
            "backfill(since=...) requires a timezone-aware datetime")

    token = os.getenv("GROUPME_ACCESS_TOKEN")
    group_id = os.getenv("GROUPME_READ_GROUP_ID")
    if not token:
        raise RuntimeError("GROUPME_ACCESS_TOKEN is not set")
    if not group_id:
        raise RuntimeError("GROUPME_READ_GROUP_ID is not set")

    db = SessionLocal()
    try:
        walk = WalkState()

        def progress(inserted, updated):
            print(f"  ... {inserted} new, {updated} refreshed")

        try:
            # Same lock as the poller: this walks and writes the very rows the
            # poller's trailing window is re-scanning, and an operator running
            # this by hand has no idea when the cron next fires.
            with advisory_lock(db, LOCK_GROUPME_INGESTION):
                inserted, updated = store_in_batches(
                    db,
                    messages_until(
                        iter_messages(group_id, token, max_pages=max_pages,
                                      walk=walk),
                        since),
                    batch_size=BATCH_SIZE,
                    on_progress=progress)

                if walk.stopped_at_ceiling:
                    # Not a success. The walk goes newest-first, so what is
                    # missing is the OLDEST end of the range - the early-season
                    # history the corpus most wants, back when the group had 252
                    # members rather than 22.
                    print(f"⚠️ Backfill INCOMPLETE: stopped at the {max_pages}-page "
                          f"ceiling after {inserted} new / {updated} refreshed, "
                          f"before reaching {since.date()}. The missing history is "
                          f"the oldest part of the range. Re-run with a larger "
                          f"--max-pages, or with a later --since and then work "
                          f"backward from there.")
                    record_job_run(
                        db, BACKFILL_GROUPME_JOB_NAME, STATUS_INCOMPLETE,
                        f"{inserted} new, {updated} refreshed; stopped at the "
                        f"{max_pages}-page ceiling before reaching {since.date()}")
                    return inserted, updated

                # record_job_run() commits, which is also what commits the
                # trailing partial batch store_in_batches() left pending.
                record_job_run(
                    db, BACKFILL_GROUPME_JOB_NAME, "success",
                    f"{inserted} new, {updated} refreshed since {since.date()}")
        except RuntimeError as exc:
            db.rollback()
            if is_lock_contention(exc):
                # Normal operation: the poller is mid-run, or another backfill
                # is. Recorded the way jobs/sheets_ingestion_shared.py does it.
                print(f"⏭️  Skipped GroupMe backfill (lock busy): {exc}")
                record_job_run(db, BACKFILL_GROUPME_JOB_NAME, "skipped",
                               f"Lock busy, will retry next run: {exc}")
                return 0, 0
            record_job_run(db, BACKFILL_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except GroupMeError as exc:
            # Already redacted at its raise site in api/groupme.py.
            db.rollback()
            record_job_run(db, BACKFILL_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except Exception as exc:
            # A KeyError from a changed GroupMe envelope is the realistic case.
            # Uncaught, it crashed the walk with a raw traceback and left no
            # record of how far the backfill got. The rollback drops only the
            # pending partial batch; committed batches stand. Type name only -
            # str(exc) on an arbitrary exception can carry a token or a raw
            # response body into job_meta. The re-raise keeps it loud.
            db.rollback()
            record_job_run(
                db, BACKFILL_GROUPME_JOB_NAME, "error",
                unexpected_error_message(exc, "GroupMe backfill"))
            raise

        print(f"✅ Backfilled {inserted} new, {updated} refreshed "
              f"since {since.date()}")
        return inserted, updated
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill GroupMe history")
    parser.add_argument("--since", default="2025-09-01",
                        help="ISO date to walk back to (default: 2025 season "
                             "start). Naive values are read as UTC; an offset "
                             "is converted, not relabelled.")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args()

    backfill(since=_parse_since(args.since), max_pages=args.max_pages)
