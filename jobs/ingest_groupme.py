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

from datetime import datetime, timedelta, timezone

from api.database import SessionLocal
from api.groupme import GroupMeError, WalkState, iter_messages
from api.job_locks import LOCK_GROUPME_INGESTION, advisory_lock
from jobs.groupme_shared import (BATCH_SIZE, ConfigurationError,
                                 is_lock_contention, messages_until, report,
                                 require_credentials, store_in_batches,
                                 unexpected_error_message)

INGEST_GROUPME_JOB_NAME = "ingest_groupme"
RESCAN_DAYS = 14
MAX_RESCAN_PAGES = 50   # 5,000 messages; a ceiling, not an expectation


def rescan_window_start(days: int = RESCAN_DAYS) -> datetime:
    """Oldest message we will re-read this run."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def run(days: int = RESCAN_DAYS) -> tuple[int, int]:
    """Fetch and upsert the trailing window. Returns (inserted, matched).

    `matched` is rows this run saw again, not rows whose content changed - see
    store_in_batches().
    """
    # The session is opened FIRST, before even reading the credentials. The
    # advisory lock has to be held for the whole fetch to actually exclude a
    # concurrent run, an exception mid-walk has to be able to reach job_meta -
    # and a rotated or revoked GROUPME_ACCESS_TOKEN used to raise out here with
    # no session open, writing no job_meta row at all. That is the same silent
    # death an envelope change used to cause, from the likelier cause.
    db = SessionLocal()
    try:
        cutoff = rescan_window_start(days=days)
        walk = WalkState()
        try:
            token, group_id = require_credentials()

            with advisory_lock(db, LOCK_GROUPME_INGESTION):
                inserted, matched = store_in_batches(
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
                    # A SUCCESS, with a caveat - deliberately not the backfill's
                    # "incomplete". The walk runs newest-first, so hitting the
                    # ceiling means every NEW message was captured; what was
                    # missed is a favorite-count refresh on the oldest tail of a
                    # window whose messages are already stored. Recording that as
                    # incomplete froze last_success_at forever, because a 252-
                    # member chat clears 5,000 messages in 14 days on any NFL
                    # Sunday and would then never advance it again.
                    caveat = (
                        f"{inserted} new, {matched} re-seen; stopped at the "
                        f"{MAX_RESCAN_PAGES}-page ceiling before the {days}-day "
                        f"window edge, so the oldest part of the window was not "
                        f"re-read and some favorite counts may be stale. New "
                        f"messages were all captured (the walk runs newest-first).")
                    print(f"⚠️ GroupMe: {caveat}")
                    report(db, INGEST_GROUPME_JOB_NAME, "success", caveat)
                    return inserted, matched

                # record_job_run() commits, which is also what commits the
                # trailing partial batch store_in_batches() left pending - the
                # rows and the bookkeeping land together.
                report(db, INGEST_GROUPME_JOB_NAME, "success",
                       f"{inserted} new, {matched} re-seen")
        except ConfigurationError as exc:
            # The ONLY exception whose text is safe to persist: built in
            # jobs/groupme_shared.py from literals and an environment variable
            # NAME. Never its value - this is the credential path.
            db.rollback()
            report(db, INGEST_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except GroupMeError as exc:
            # Redacted at its raise site in api/groupme.py.
            db.rollback()
            report(db, INGEST_GROUPME_JOB_NAME, "error", str(exc))
            raise
        except RuntimeError as exc:
            db.rollback()
            if is_lock_contention(exc):
                # Normal operation, not a failure: the other run is doing the
                # work. Same treatment as jobs/sheets_ingestion_shared.py.
                print(f"⏭️  Skipped GroupMe ingestion (lock busy): {exc}")
                report(db, INGEST_GROUPME_JOB_NAME, "skipped",
                       f"Lock busy, will retry next run: {exc}")
                return 0, 0
            # Every OTHER RuntimeError is somebody else's - requests and psycopg
            # both raise them with a URL or a connection string in the message.
            # This branch used to log str(exc) on the grounds that the only
            # RuntimeErrors here were our own credential checks; those are
            # ConfigurationErrors now, so the justification is gone with them.
            report(db, INGEST_GROUPME_JOB_NAME, "error",
                   unexpected_error_message(exc, "GroupMe ingestion"))
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
            report(db, INGEST_GROUPME_JOB_NAME, "error",
                   unexpected_error_message(exc, "GroupMe ingestion"))
            raise

        print(f"✅ GroupMe: {inserted} new, {matched} re-seen")
        return inserted, matched
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
