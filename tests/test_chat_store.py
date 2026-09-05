"""Upserting GroupMe messages.

The favorite count is why this is an upsert and not an insert. A message
accrues likes for hours or days after posting, and the corpus is ranked by
likes, so an insert-once poller would permanently undercount exactly the
material the recap bot learns its voice from.
"""

from api.chat_store import upsert_messages
from api.models import ChatMessage


def raw(mid, favs=0, system=False, text="hi", sender_type="user"):
    return {
        "id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
        "sender_type": sender_type, "text": text, "system": system,
        "favorited_by": ["x"] * favs, "created_at": 1700000000,
    }


def test_inserts_new_messages(db):
    inserted, updated = upsert_messages(db, [raw("m1"), raw("m2")])
    assert (inserted, updated) == (2, 0)
    assert db.query(ChatMessage).count() == 2


def test_reingesting_the_same_message_updates_its_favorite_count(db):
    upsert_messages(db, [raw("m1", favs=1)])
    inserted, updated = upsert_messages(db, [raw("m1", favs=7)])

    assert (inserted, updated) == (0, 1)
    assert db.query(ChatMessage).one().favorite_count == 7


def test_favorited_by_length_becomes_the_count(db):
    upsert_messages(db, [raw("m1", favs=3)])
    assert db.query(ChatMessage).one().favorite_count == 3


def test_system_flag_and_null_text_survive(db):
    """Removal notices carry system=True and can have no text."""
    payload = raw("m1", system=True, sender_type="system")
    payload["text"] = None
    upsert_messages(db, [payload])

    row = db.query(ChatMessage).one()
    assert row.is_system is True
    assert row.text is None


def test_created_at_is_converted_from_unix_seconds(db):
    upsert_messages(db, [raw("m1")])
    assert db.query(ChatMessage).one().created_at.year == 2023


def test_duplicate_ids_within_one_batch_do_not_double_insert(db):
    """Trailing-window re-scans overlap, so a batch can contain repeats."""
    inserted, updated = upsert_messages(db, [raw("m1", favs=1), raw("m1", favs=4)])
    assert inserted == 1
    assert db.query(ChatMessage).one().favorite_count == 4
