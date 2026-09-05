"""Poll the pool's GroupMe and keep chat_messages current.

Re-scans a trailing window on every run rather than fetching only what is new.
Favorite counts rise for hours or days after a message posts, and the recap
bot's voice corpus is ranked by them, so a high-water-mark poller would freeze
every count at its value seconds after posting.

Read-only against GroupMe. Posting is GRPM-4 and lives elsewhere.

Outage remedy: the window is trailing, not cumulative, so this job cannot
self-heal a gap. If it stops running for longer than RESCAN_DAYS, every
message older than the window on the next successful run is simply never
ingested. Repair that with jobs/backfill_groupme.py --since <the date the
outage began>; re-running this poller will not recover it.
"""

import os
from datetime import datetime, timedelta, timezone

from api.database import SessionLocal
from api.groupme import GroupMeError, WalkState, iter_messages
from api.job_locks import LOCK_GROUPME_INGESTION, advisory_lock
from jobs.groupme_shared import (BATCH_SIZE, STATUS_INCOMPLETE,
                                 is_lock_contention, messages_until,
                                 store_in_batches, unexpected_error_message)
from jobs.sheets_ingestion_shared import record_job_run

INGEST_GROUPME_JOB_NAME = "ingest_groupme"
RESCAN_DAYS = 14
MAX_RESCAN_PAGES = 50   # 5,000 messages; a ceiling, not an expectation


def _credentials() -> tuple[str, str]:
    token = os.getenv("GROUPME_ACCESS_TOKEN")
    group_id = os.getenv("GROUPME_READ_GROUP_ID")
    if not token:
        raise RuntimeError("GROUPME_ACCESS_TOKEN is not set")
    if not group_id:
        raise RuntimeError("GROUPME_READ_GROUP_ID is not set")
    return token, group_id


def rescan_window_start(days: int = RESCAN_DAYS) -> datetime:
    """Oldest message we will re-read this run."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def run(days: int = RESCAN_DAYS) -> tuple[int, int]:
    """Fetch and upsert the trailing window. Returns (inserted, updated)."""
    token, group_id = _credentials()

    # The session is opened before the network walk on purpose. The advisory
    # lock has to be held for the whole fetch to actually exclude a concurrent
    # run, and an exception mid-walk has to be able to reach job_meta. What the
    # batching below buys is that the session is no longer idle-IN-TRANSACTION
    # across the whole rate-limited walk: each batch commit ends the
    # transaction, so the longest open transaction is one batch of paging.
    db = SessionLocal()
    try:
        cutoff = rescan_window_start(days=days)
        walk = WalkState()
        try:
            with advisory_lock(db, LOCK_GROUPME_INGESTION):
                inserted, updated = store_in_batches(
                    db,
                    messages_until(
                        iter_messages(group_id, token,
                                      max_pages=MAX_RESCAN_PAGES, walk=walk),
                        cutoff),
                    batch_size=BATCH_SIZE)

                # WalkState is the only reliable signal here. The old heuristic
                # - "did we see MAX_RESCAN_PAGES * PAGE_LIMIT messages?" - was a
                # guaranteed false negative whenever any page came back short of
                # PAGE_LIMIT, which GroupMe does routinely.
                if walk.stopped_at_ceiling:
                    print(f"⚠️ GroupMe: hit the {MAX_RESCAN_PAGES}-page ceiling "
                          f"before reaching the {days}-day window edge; some "
                          f"favorite counts may not have refreshed this run")
                    # Not "success": the window was not fully covered, so
                    # last_success_at must not advance on the strength of it.
                    record_job_run(
                        db, INGEST_GROUPME_JOB_NAME, STATUS_INCOMPLETE,
                        f"{inserted} new, {updated} refreshed; stopped at the "
                        f"{MAX_RESCAN_PAGES}-page ceiling before the "
                        f"{days}-day window edge")
                    return inserted, updated

                # record_job_run() commits, which is also what commits the
                # trailing partial batch store_in_batches() left pending - the
                # rows and the bookkeeping land together.
                record_job_run(db, INGEST_GROUPME_JOB_NAME, "success",
                               f"{inserted} new, {updated} refreshed")
        except RuntimeError as exc:
            db.rollback()
            if is_lock_contention(exc):
                # Normal operation, not a failure: the other run is doing the
                # work. Same treatment as jobs/sheets_ingestion_shared.py.
                print(f"⏭️  Skipped GroupMe ingestion (lock busy): {exc}")
                record_job_run(db, INGEST_GROUPME_JOB_NAME, "skipped",
                               f"Lock busy, will retry next run: {exc}")
                return 0, 0
            # Our own literal messages (the credential checks), so safe to log.
            record_job_run(db, INGEST_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except GroupMeError as exc:
            # Redacted at its raise site in api/groupme.py.
            db.rollback()
            record_job_run(db, INGEST_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except Exception as exc:
            # Anything else - most realistically a KeyError from a changed
            # GroupMe envelope, since the client and chat_store index
            # ["response"], ["created_at"] and ["id"] directly. Left uncaught
            # this wrote NO job_meta row at all, so monitoring kept reading the
            # last success while the job died in a Railway traceback nobody
            # opens. The rollback drops only the pending partial batch;
            # committed batches stand. The re-raise keeps the traceback.
            db.rollback()
            record_job_run(
                db, INGEST_GROUPME_JOB_NAME, "error",
                unexpected_error_message(exc, "GroupMe ingestion"))
            raise

        print(f"✅ GroupMe: {inserted} new, {updated} refreshed")
        return inserted, updated
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Poll GroupMe into chat_messages")
    parser.add_argument("--days", type=int, default=RESCAN_DAYS,
                        help="how far back to re-scan for favorite-count changes")
    args = parser.parse_args()

    run(days=args.days)
