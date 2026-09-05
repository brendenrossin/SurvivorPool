"""One-time walk back through GroupMe history to the season start.

Run once per season, not on a cron. The poller in ingest_groupme.py keeps
things current afterwards.
"""

import os
from datetime import datetime, timezone

from api.chat_store import upsert_messages
from api.database import SessionLocal
from api.groupme import iter_messages

MAX_PAGES = 500          # 50k messages; a ceiling, not an expectation
BATCH_SIZE = 200


def backfill(since: datetime, max_pages: int = MAX_PAGES) -> int:
    """Store every message posted on or after `since`. Returns the count."""
    token = os.getenv("GROUPME_ACCESS_TOKEN")
    group_id = os.getenv("GROUPME_READ_GROUP_ID")
    if not token:
        raise RuntimeError("GROUPME_ACCESS_TOKEN is not set")
    if not group_id:
        raise RuntimeError("GROUPME_READ_GROUP_ID is not set")

    db = SessionLocal()
    try:
        stored = 0
        batch = []

        for message in iter_messages(group_id, token, max_pages=max_pages):
            created = datetime.fromtimestamp(message["created_at"], tz=timezone.utc)
            if created < since:
                break
            batch.append(message)

            if len(batch) >= BATCH_SIZE:
                inserted, updated = upsert_messages(db, batch)
                stored += inserted + updated
                print(f"  ... {stored} messages")
                batch = []

        if batch:
            inserted, updated = upsert_messages(db, batch)
            stored += inserted + updated

        print(f"✅ Backfilled {stored} messages since {since.date()}")
        return stored
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill GroupMe history")
    parser.add_argument("--since", default="2025-09-01",
                        help="ISO date to walk back to (default: 2025 season start)")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args()

    backfill(
        since=datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc),
        max_pages=args.max_pages,
    )
