"""Poll the pool's GroupMe and keep chat_messages current.

Re-scans a trailing window on every run rather than fetching only what is new.
Favorite counts rise for hours or days after a message posts, and the recap
bot's voice corpus is ranked by them, so a high-water-mark poller would freeze
every count at its value seconds after posting.

Read-only against GroupMe. Posting is GRPM-4 and lives elsewhere.
"""

import os
from datetime import datetime, timedelta, timezone

from api.chat_store import upsert_messages
from api.database import SessionLocal
from api.groupme import PAGE_LIMIT, GroupMeError, iter_messages
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

    db = SessionLocal()
    try:
        cutoff = rescan_window_start(days=days)
        try:
            batch = []
            total_seen = 0
            reached_window_edge = False
            for message in iter_messages(group_id, token, max_pages=MAX_RESCAN_PAGES):
                total_seen += 1
                created = datetime.fromtimestamp(message["created_at"], tz=timezone.utc)
                if created < cutoff:
                    reached_window_edge = True
                    break
                batch.append(message)

            if not reached_window_edge and total_seen >= MAX_RESCAN_PAGES * PAGE_LIMIT:
                # The page ceiling stopped the walk before it reached the
                # window edge, not the cutoff check - so the window was not
                # fully covered and some favorite counts may be stale.
                print(f"⚠️ GroupMe: hit the {MAX_RESCAN_PAGES}-page ceiling before "
                      f"reaching the {days}-day window edge; some favorite counts "
                      f"may not have refreshed this run")

            inserted, updated = upsert_messages(db, batch)
        except (GroupMeError, RuntimeError) as exc:
            record_job_run(db, INGEST_GROUPME_JOB_NAME, "error", str(exc))
            raise

        record_job_run(db, INGEST_GROUPME_JOB_NAME, "success",
                       f"{inserted} new, {updated} refreshed")
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
