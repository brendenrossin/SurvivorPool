"""chat_messages stores the pool's GroupMe history.

Favorite counts are mutable: a message accrues likes for hours or days after
it posts, so the column has to be updatable rather than write-once. See
`upsert_messages` in api/chat_store.py.
"""

from datetime import datetime, timezone

from api.models import ChatMessage


def test_chat_message_round_trips(db):
    db.add(ChatMessage(
        message_id="m1",
        group_id="g1",
        sender_id="u1",
        sender_name="Ryan Chong",
        sender_type="user",
        text="lock of the week",
        favorite_count=3,
        is_system=False,
        created_at=datetime(2025, 10, 5, 17, 0, tzinfo=timezone.utc),
    ))
    db.commit()

    row = db.query(ChatMessage).one()
    assert row.message_id == "m1"
    assert row.favorite_count == 3
    assert row.is_system is False


def test_system_messages_are_storable(db):
    """Removal notices are the elimination signal and the meme trigger, so they
    are kept even though the voice corpus filters them out."""
    db.add(ChatMessage(
        message_id="m2",
        group_id="g1",
        sender_id=None,
        sender_name="GroupMe",
        sender_type="system",
        text="Travis removed Ryan Chong from the group",
        favorite_count=0,
        is_system=True,
        created_at=datetime(2025, 10, 6, 3, 0, tzinfo=timezone.utc),
    ))
    db.commit()
    assert db.query(ChatMessage).filter_by(is_system=True).count() == 1


def test_the_corpus_index_matches_the_migration_sql():
    """Tests build this schema from api/models.py on SQLite; production builds
    it from db/migrations.sql on Postgres. Nothing else compares the two, so an
    index added to one and not the other is invisible until a slow query.
    """
    import re
    from pathlib import Path

    from api.models import ChatMessage

    index = {ix.name: ix for ix in ChatMessage.__table__.indexes}["idx_chat_messages_corpus"]
    predicate = str(index.dialect_options["postgresql"]["where"])

    sql = Path(__file__).resolve().parent.parent.joinpath("db/migrations.sql").read_text()
    declared = re.search(
        r"CREATE INDEX IF NOT EXISTS idx_chat_messages_corpus\s+"
        r"ON chat_messages \((?P<cols>[^)]*)\)\s+WHERE (?P<where>[^;]+);", sql)

    assert declared, "idx_chat_messages_corpus is missing from db/migrations.sql"
    assert declared.group("cols").strip() == "favorite_count DESC, created_at"
    assert declared.group("where").strip() == predicate

    # The two single-column indexes this replaced served neither the filter nor
    # the sort of the corpus query fully.
    assert "idx_chat_messages_favorites ON" not in sql
    assert "idx_chat_messages_created_at ON" not in sql
