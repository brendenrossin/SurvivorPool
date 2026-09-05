"""Translate GroupMe payloads into chat_messages rows.

Separate from api/groupme.py so this is testable with no network and that is
testable with no database.
"""

from datetime import datetime, timezone

from api.models import ChatMessage


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


def upsert_messages(db, raw_messages) -> tuple[int, int]:
    """Insert new messages, refresh favorite counts on ones already stored.

    Returns:
        (inserted, updated)
    """
    inserted = 0
    updated = 0

    for payload in raw_messages:
        message_id = payload["id"]
        values = _to_row_values(payload)

        row = db.query(ChatMessage).filter_by(message_id=message_id).one_or_none()
        if row is None:
            db.add(ChatMessage(message_id=message_id, **values))
            db.flush()          # so a repeat inside this same batch is found below
            inserted += 1
        else:
            for key, value in values.items():
                setattr(row, key, value)
            updated += 1

    db.commit()
    return inserted, updated
