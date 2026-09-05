"""Upserting GroupMe messages.

The favorite count is why this is an upsert and not an insert. A message
accrues likes for hours or days after posting, and the corpus is ranked by
likes, so an insert-once poller would permanently undercount exactly the
material the recap bot learns its voice from.

`upsert_messages` does not commit - the caller owns the transaction - so these
tests commit for themselves, exactly as the jobs now do.
"""

from sqlalchemy import event

from api.chat_store import ID_CHUNK_SIZE, upsert_messages
from api.models import ChatMessage


def raw(mid, favs=0, system=False, text="hi", sender_type="user"):
    return {
        "id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
        "sender_type": sender_type, "text": text, "system": system,
        "favorited_by": ["x"] * favs, "created_at": 1700000000,
    }


def test_inserts_new_messages(db):
    inserted, updated = upsert_messages(db, [raw("m1"), raw("m2")])
    db.commit()
    assert (inserted, updated) == (2, 0)
    assert db.query(ChatMessage).count() == 2


def test_reingesting_the_same_message_updates_its_favorite_count(db):
    upsert_messages(db, [raw("m1", favs=1)])
    db.commit()
    inserted, updated = upsert_messages(db, [raw("m1", favs=7)])
    db.commit()

    assert (inserted, updated) == (0, 1)
    assert db.query(ChatMessage).one().favorite_count == 7


def test_favorited_by_length_becomes_the_count(db):
    upsert_messages(db, [raw("m1", favs=3)])
    db.commit()
    assert db.query(ChatMessage).one().favorite_count == 3


def test_system_flag_and_null_text_survive(db):
    """Removal notices carry system=True and can have no text."""
    payload = raw("m1", system=True, sender_type="system")
    payload["text"] = None
    upsert_messages(db, [payload])
    db.commit()

    row = db.query(ChatMessage).one()
    assert row.is_system is True
    assert row.text is None


def test_created_at_is_converted_from_unix_seconds(db):
    upsert_messages(db, [raw("m1")])
    db.commit()
    assert db.query(ChatMessage).one().created_at.year == 2023


def test_duplicate_ids_within_one_batch_do_not_double_insert(db):
    """Trailing-window re-scans overlap, so a batch can contain repeats."""
    inserted, updated = upsert_messages(db, [raw("m1", favs=1), raw("m1", favs=4)])
    db.commit()
    assert inserted == 1
    assert db.query(ChatMessage).one().favorite_count == 4


def test_duplicate_ids_in_one_batch_under_production_session_semantics(db):
    """The in-batch dedupe is load-bearing in production.

    tests/conftest.py builds its session with SQLAlchemy's default
    autoflush=True, which masks the problem: a lookup query auto-flushes any
    pending add, so a repeated id inside one batch is found whether or not the
    store handles it. api/database.py builds SessionLocal with autoflush=False,
    so production has no such safety net - a batch that added the same id twice
    would raise on the primary key at commit. The poller re-scans an overlapping
    window, so a batch containing the same id twice is normal input, not an edge
    case.

    This test pins the production configuration so losing the dedupe fails here
    instead of in production.
    """
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db.get_bind(), autoflush=False)
    session = Session()
    try:
        inserted, updated = upsert_messages(
            session, [raw("m1", favs=1), raw("m1", favs=4)])
        session.commit()

        assert inserted == 1
        assert session.query(ChatMessage).one().favorite_count == 4
    finally:
        session.close()


def test_the_store_does_not_own_the_transaction(db):
    """Nothing is durable until the caller commits, so a job can pair the rows
    with its own job_meta write in one transaction."""
    upsert_messages(db, [raw("m1")])
    db.rollback()

    assert db.query(ChatMessage).count() == 0


def _count_queries(db, work):
    """SELECT/INSERT/UPDATE statements issued while `work` runs."""
    engine = db.get_bind()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        work()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return statements


def test_lookup_cost_does_not_scale_with_batch_size(db):
    """This was one SELECT per message plus a flush per insert. The poller can
    hand it 5,000 messages several times an hour, which is thousands of round
    trips for what is one IN query."""
    small = _count_queries(db, lambda: upsert_messages(
        db, [raw(f"s{i}") for i in range(3)]))
    db.commit()

    large = _count_queries(db, lambda: upsert_messages(
        db, [raw(f"l{i}") for i in range(300)]))
    db.commit()

    assert len(small) == 1
    assert len(large) == len(small)


def test_a_batch_larger_than_the_chunk_size_is_chunked_not_one_giant_in(db):
    """A single IN list of thousands of ids is how you find a driver's bound
    parameter ceiling in production."""
    n = ID_CHUNK_SIZE * 2 + 1
    statements = _count_queries(db, lambda: upsert_messages(
        db, [raw(f"c{i}") for i in range(n)]))
    db.commit()

    assert len(statements) == 3
    assert db.query(ChatMessage).count() == n
