"""One-time walk back through GroupMe history to the season start.

Run once per season, not on a cron. The poller in ingest_groupme.py keeps
things current afterwards.
"""

import os
from datetime import datetime, timezone

from api.chat_store import upsert_messages
from api.database import SessionLocal
from api.groupme import WalkState, iter_messages

MAX_PAGES = 500          # 50k messages; a ceiling, not an expectation
BATCH_SIZE = 200


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


def backfill(since: datetime, max_pages: int = MAX_PAGES) -> int:
    """Store every message posted on or after `since`. Returns the count."""
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
        stored = 0
        batch = []
        walk = WalkState()

        for message in iter_messages(group_id, token, max_pages=max_pages,
                                     walk=walk):
            created = datetime.fromtimestamp(message["created_at"], tz=timezone.utc)
            if created < since:
                break
            batch.append(message)

            if len(batch) >= BATCH_SIZE:
                inserted, updated = upsert_messages(db, batch)
                db.commit()     # upsert_messages leaves the transaction to us
                stored += inserted + updated
                print(f"  ... {stored} messages")
                batch = []

        if batch:
            inserted, updated = upsert_messages(db, batch)
            db.commit()     # upsert_messages leaves the transaction to us
            stored += inserted + updated

        if walk.stopped_at_ceiling:
            # Not a success. The walk goes newest-first, so what is missing is
            # the OLDEST end of the range - the early-season history the corpus
            # most wants, back when the group had 252 members rather than 22.
            print(f"⚠️ Backfill INCOMPLETE: stopped at the {max_pages}-page "
                  f"ceiling after {stored} messages, before reaching "
                  f"{since.date()}. The missing history is the oldest part of "
                  f"the range. Re-run with a larger --max-pages, or with a "
                  f"later --since and then work backward from there.")
        else:
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
                        help="ISO date to walk back to (default: 2025 season "
                             "start). Naive values are read as UTC; an offset "
                             "is converted, not relabelled.")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = parser.parse_args()

    backfill(since=_parse_since(args.since), max_pages=args.max_pages)
