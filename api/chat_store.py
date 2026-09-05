"""Translate GroupMe payloads into chat_messages rows.

Separate from api/groupme.py so this is testable with no network and that is
testable with no database.
"""

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from api.models import ChatMessage

# Postgres accepts far more bound parameters than this, but a 5,000-message
# poller run would still be a single absurd IN list, and psycopg's limit is not
# something to discover in production at 2am.
ID_CHUNK_SIZE = 500


def _to_row_values(payload: dict) -> dict:
    return {
        "group_id": payload.get("group_id"),
        "sender_id": payload.get("user_id"),
        "sender_name": payload.get("name"),
        "sender_type": payload.get("sender_type"),
        "text": payload.get("text"),
        "favorite_count": len(payload.get("favorited_by") or []),
        "is_system": bool(payload.get("system")),
        "created_at": datetime.fromtimestamp(payload["created_at"], tz=timezone.utc),
    }


def upsert_messages(db: Session,
                    raw_messages: Iterable[dict]) -> tuple[int, int]:
    """Insert new messages, refresh favorite counts on ones already stored.

    One SELECT per chunk of ids rather than one per message: the poller hands
    this up to 5,000 messages several times an hour, and the per-message lookup
    plus per-insert flush it replaced made that thousands of round trips.

    Does NOT commit - the caller owns the transaction, so a run can pair these
    rows with its own job_meta bookkeeping atomically.

    Returns:
        (inserted, updated)
    """
    # Deduplicate before touching the database, last occurrence winning. The
    # poller re-scans an overlapping window, so a repeated id inside one batch
    # is normal input; the later copy is the fresher favorite count. Doing this
    # up front is also what makes the batch safe under autoflush=False, which
    # is production's setting: nothing pending has to be found by a query.
    by_id: dict[str, dict] = {}
    for payload in raw_messages:
        by_id[payload["id"]] = _to_row_values(payload)

    if not by_id:
        return 0, 0

    ids = list(by_id)
    existing: dict[str, ChatMessage] = {}
    for start in range(0, len(ids), ID_CHUNK_SIZE):
        chunk = ids[start:start + ID_CHUNK_SIZE]
        for row in db.query(ChatMessage).filter(
                ChatMessage.message_id.in_(chunk)).all():
            existing[row.message_id] = row

    inserted = 0
    updated = 0

    for message_id, values in by_id.items():
        row = existing.get(message_id)
        if row is None:
            db.add(ChatMessage(message_id=message_id, **values))
            inserted += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
            updated += 1

    return inserted, updated
