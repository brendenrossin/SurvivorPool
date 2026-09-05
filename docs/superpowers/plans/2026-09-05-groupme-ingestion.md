# GRPM-1: GroupMe ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the pool's GroupMe history into Postgres, with favorite counts that stay current, so later tickets can build a voice corpus from it.

**Architecture:** A thin `requests`-based read client (`api/groupme.py`) wrapping GroupMe's v3 message endpoint, a `chat_messages` table, an idempotent upsert, a poller job that re-scans a trailing window so favorite counts keep rising, and a one-time backfill that walks `before_id` back to the 2025 season start.

**Tech Stack:** Python 3.11, `requests==2.31.0`, SQLAlchemy, Postgres (SQLite in tests), pytest 8.4.2.

**Spec:** `docs/design/groupme-recap-spec.md`

## Global Constraints

- **Read-only.** GRPM-1 introduces no posting. `POST /v3/bots/post` is GRPM-4's job. Nothing in this ticket may write to GroupMe.
- **`api/` holds providers and domain logic; `jobs/` holds workers; `app/` is Streamlit view code only.** Nothing from this ticket lands in `app/`.
- Reuse `api/rate_limiter.py` (`get_rate_limiter()`, `APIRateLimiter.wait_if_needed()`). Do not add a second throttle.
- Jobs record their outcome via `record_job_run(db, job_name, status, message)` from `jobs/sheets_ingestion_shared.py`. A job that does not write `job_meta` is invisible to monitoring.
- Session cleanup uses the project's `try/finally` pattern (CLAUDE.md § Database Connection Leaks).
- Tests run on in-memory SQLite via the `db` fixture in `tests/conftest.py`. No test may make a network call.
- Secrets come from env vars only: `GROUPME_ACCESS_TOKEN`, `GROUPME_READ_GROUP_ID`. Never commit a token, never log one.
- There is **no `Makefile`** in this repo despite what the dev-workflow skill assumes. The check command is `python -m pytest tests/ -q`.

---

## File Structure

| File | Responsibility |
|---|---|
| `api/groupme.py` (create) | HTTP client. Fetch and page messages. Knows GroupMe's envelope, knows nothing about our schema. |
| `api/models.py` (modify) | Add `ChatMessage`. |
| `db/migrations.sql` (modify) | Add `chat_messages` DDL + indexes. |
| `api/chat_store.py` (create) | `upsert_messages(db, raw)`. Translates GroupMe payloads into rows. Knows our schema, makes no HTTP calls. |
| `jobs/ingest_groupme.py` (create) | Poller. Trailing-window re-scan. |
| `jobs/backfill_groupme.py` (create) | One-time historical walk. |
| `scripts/groupme_retention_probe.py` (create) | Task 1 gate. Throwaway-grade but committed, since the answer needs to be reproducible. |

The client/store split matters: it is what lets Tasks 3 and 4 be unit-tested with zero network and zero mocking of our own database.

---

## Task 1: Credentials and the retention probe (BLOCKING GATE)

**This task gates the entire epic and needs the owner.** The spec's open risk: most of the 2025 chat was written by players Travis removed from the group when they busted. If GroupMe purges a removed member's messages, the voice corpus is survivor-only and far thinner than GRPM-3 assumes.

**Files:**
- Create: `scripts/groupme_retention_probe.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: nothing.
- Produces: a documented yes/no on message retention, and confirmation of the live response envelope that Task 3 parses.

- [ ] **Step 1: Owner obtains a token**

The owner logs in at `https://dev.groupme.com/`, opens "Access Token" in the top nav, and copies the token. This is a personal user token that can read any group the owner belongs to. Find the group id from `https://dev.groupme.com/groups`.

Add both to `.env` (never commit):

```
GROUPME_ACCESS_TOKEN="..."
GROUPME_READ_GROUP_ID="..."
```

- [ ] **Step 2: Add the names to `.env.example`**

```
GROUPME_ACCESS_TOKEN=
GROUPME_READ_GROUP_ID=
```

- [ ] **Step 3: Write the probe**

```python
"""Answer one question: do removed members' messages survive removal?

GRPM-3's voice corpus is built from the group's most-liked messages, and most
of the 2025 season was written by players who have since been removed from the
group for busting. If GroupMe purges them, the corpus is survivor-only and the
few-shot strategy in the spec needs rethinking.

Read-only. Makes no writes to GroupMe and none to our database.
"""

import os
import requests
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.groupme.com/v3"


def main():
    token = os.environ["GROUPME_ACCESS_TOKEN"]
    group_id = os.environ["GROUPME_READ_GROUP_ID"]

    members = requests.get(
        f"{BASE}/groups/{group_id}", params={"token": token}, timeout=30
    ).json()["response"]["members"]
    current_ids = {m["user_id"] for m in members}
    print(f"current members: {len(current_ids)}")

    # Walk back 500 messages and see how many authors are no longer members.
    seen = Counter()
    before_id = None
    pages = 0
    while pages < 5:
        params = {"token": token, "limit": 100}
        if before_id:
            params["before_id"] = before_id
        resp = requests.get(f"{BASE}/groups/{group_id}/messages", params=params, timeout=30)
        if resp.status_code == 304:
            print("reached start of history")
            break
        resp.raise_for_status()
        msgs = resp.json()["response"]["messages"]
        if not msgs:
            break
        for m in msgs:
            seen[m["user_id"]] += 1
        before_id = msgs[-1]["id"]
        pages += 1

    authors = set(seen)
    departed = authors - current_ids
    print(f"distinct authors in last {sum(seen.values())} messages: {len(authors)}")
    print(f"authors no longer in the group: {len(departed)}")
    print(f"their messages still visible: {sum(seen[a] for a in departed)}")
    print("\nVERDICT:", "RETAINED" if departed else "INCONCLUSIVE (no departed authors in sample)")

    sample = msgs[0]
    print("\nEnvelope keys (Task 3 parses these):", sorted(sample.keys()))
    print("sender_type:", sample.get("sender_type"), "| system:", sample.get("system"))
    print("favorited_by is a list:", isinstance(sample.get("favorited_by"), list))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run it**

Run: `python scripts/groupme_retention_probe.py`

Expected: prints a verdict and the live envelope keys.

**If the verdict is not RETAINED, STOP and report to the owner.** GRPM-3's approach changes and the spec needs revision before more code is written. Do not proceed to Task 2 on a purge result.

Also record the printed envelope keys — Task 3's parser is written against my documented understanding of GroupMe's shape, and this is the step that confirms it. If `sender_type`, `system`, or `favorited_by` differ from what Task 3 expects, fix Task 3's parser to match reality rather than the plan.

- [ ] **Step 5: Commit**

```bash
git add scripts/groupme_retention_probe.py .env.example
git commit -m "🔍 Probe whether removed members' GroupMe messages survive removal"
```

---

## Task 2: `chat_messages` table

**Files:**
- Modify: `api/models.py`
- Modify: `db/migrations.sql`
- Test: `tests/test_chat_messages.py`

**Interfaces:**
- Consumes: `Base` from `api/database.py`.
- Produces: `ChatMessage` with columns `message_id: str` (PK), `group_id: str`, `sender_id: str | None`, `sender_name: str | None`, `sender_type: str | None`, `text: str | None`, `favorite_count: int`, `is_system: bool`, `created_at: datetime`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chat_messages.py -q`
Expected: FAIL with `ImportError: cannot import name 'ChatMessage' from 'api.models'`

- [ ] **Step 3: Add the model**

Append to `api/models.py`:

```python
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id = Column(String, primary_key=True)   # GroupMe's own id
    group_id = Column(String, nullable=False)
    sender_id = Column(String)
    sender_name = Column(String)
    sender_type = Column(String)                    # "user" | "bot" | "system"
    text = Column(String)
    favorite_count = Column(Integer, nullable=False, default=0)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
```

Check the existing import line at the top of `api/models.py` already brings in `Boolean`, `Column`, `DateTime`, `Integer`, `String`. Add any that are missing.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_chat_messages.py -q`
Expected: 2 passed

- [ ] **Step 5: Add the migration**

Append to `db/migrations.sql`:

```sql
-- GroupMe chat history, source of the recap bot's voice corpus
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    sender_id TEXT,
    sender_name TEXT,
    sender_type TEXT,
    text TEXT,
    favorite_count INT NOT NULL DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL
);

-- corpus reads are "most-liked, before a cutoff"
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_favorites ON chat_messages(favorite_count DESC);
```

- [ ] **Step 6: Commit**

```bash
git add api/models.py db/migrations.sql tests/test_chat_messages.py
git commit -m "🗃️ Add chat_messages for GroupMe history"
```

---

## Task 3: GroupMe read client

**Files:**
- Create: `api/groupme.py`
- Test: `tests/test_groupme_client.py`

**Interfaces:**
- Consumes: `get_rate_limiter()` from `api/rate_limiter.py`.
- Produces:
  - `fetch_message_page(group_id, token, before_id=None, limit=100) -> list[dict]` — one page, newest first, `[]` at end of history.
  - `iter_messages(group_id, token, stop_before=None, max_pages=None) -> Iterator[dict]` — pages backward, yielding raw GroupMe dicts.
  - `GroupMeError(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
"""The GroupMe client pages backward through history.

GroupMe returns messages newest-first and signals "no more history" with a
304, not an empty list, so a client that only checks for `[]` walks forever.
"""

import pytest

from api import groupme


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


def _page(ids):
    return {"response": {"messages": [
        {"id": i, "group_id": "g1", "user_id": "u1", "name": "Someone",
         "sender_type": "user", "text": f"msg {i}", "system": False,
         "favorited_by": [], "created_at": 1700000000}
        for i in ids
    ]}}


def test_fetch_message_page_returns_messages(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["3", "2", "1"])))
    out = groupme.fetch_message_page("g1", "tok")
    assert [m["id"] for m in out] == ["3", "2", "1"]


def test_304_means_end_of_history(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: FakeResponse(304))
    assert groupme.fetch_message_page("g1", "tok", before_id="1") == []


def test_iter_messages_pages_backward_until_exhausted(monkeypatch):
    pages = [_page(["5", "4"]), _page(["3", "2"]), None]
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params.get("before_id"))
        nxt = pages.pop(0)
        return FakeResponse(200, nxt) if nxt else FakeResponse(304)

    monkeypatch.setattr(groupme.requests, "get", fake_get)
    ids = [m["id"] for m in groupme.iter_messages("g1", "tok")]
    assert ids == ["5", "4", "3", "2"]
    assert calls == [None, "4", "2"]   # before_id is the oldest id of the prior page


def test_iter_messages_stops_at_stop_before(monkeypatch):
    """The poller only re-scans a trailing window; it must not walk all history."""
    monkeypatch.setattr(groupme.requests, "get",
                        lambda *a, **k: FakeResponse(200, _page(["9", "8", "7"])))
    ids = [m["id"] for m in groupme.iter_messages("g1", "tok", stop_before="8")]
    assert ids == ["9"]


def test_http_error_raises_groupme_error(monkeypatch):
    monkeypatch.setattr(groupme.requests, "get", lambda *a, **k: FakeResponse(500))
    with pytest.raises(groupme.GroupMeError):
        groupme.fetch_message_page("g1", "tok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_groupme_client.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.groupme'`

- [ ] **Step 3: Write the client**

```python
"""Read-only GroupMe v3 client.

Knows GroupMe's response envelope and nothing about our schema; translation
into rows lives in api/chat_store.py. Read-only by design - posting arrives in
GRPM-4 and belongs in a separate function with a separate credential.

GroupMe pages backward: you pass the oldest id you have seen as `before_id`
and get the 100 before that, newest-first. The end of history is a 304, not an
empty list.
"""

from typing import Iterator, Optional

import requests

from api.rate_limiter import get_rate_limiter

BASE_URL = "https://api.groupme.com/v3"
PAGE_LIMIT = 100
TIMEOUT = 30


class GroupMeError(Exception):
    """A GroupMe request failed."""


def fetch_message_page(group_id: str, token: str,
                       before_id: Optional[str] = None,
                       limit: int = PAGE_LIMIT) -> list[dict]:
    """One page of messages, newest first. Empty list at the end of history."""
    get_rate_limiter().wait_if_needed()

    params = {"token": token, "limit": limit}
    if before_id:
        params["before_id"] = before_id

    try:
        resp = requests.get(f"{BASE_URL}/groups/{group_id}/messages",
                            params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GroupMeError(f"GroupMe request failed: {exc}") from exc

    if resp.status_code == 304:
        return []
    if resp.status_code >= 400:
        raise GroupMeError(f"GroupMe returned HTTP {resp.status_code}")

    return resp.json()["response"]["messages"]


def iter_messages(group_id: str, token: str,
                  stop_before: Optional[str] = None,
                  max_pages: Optional[int] = None) -> Iterator[dict]:
    """Walk history backward, newest first.

    Args:
        stop_before: stop once this message id is reached. The poller passes
            the newest id it already has so it re-scans only a trailing window.
        max_pages: hard ceiling, so a bug cannot page forever.
    """
    before_id = None
    pages = 0

    while max_pages is None or pages < max_pages:
        page = fetch_message_page(group_id, token, before_id=before_id)
        if not page:
            return

        for message in page:
            if stop_before is not None and message["id"] == stop_before:
                return
            yield message

        before_id = page[-1]["id"]
        pages += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_groupme_client.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add api/groupme.py tests/test_groupme_client.py
git commit -m "🔌 Add a read-only GroupMe client that pages backward"
```

---

## Task 4: Message upsert

**Files:**
- Create: `api/chat_store.py`
- Test: `tests/test_chat_store.py`

**Interfaces:**
- Consumes: `ChatMessage` (Task 2).
- Produces: `upsert_messages(db, raw_messages) -> tuple[int, int]` returning `(inserted, updated)`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_chat_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.chat_store'`

- [ ] **Step 3: Write the store**

```python
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
```

Note the `db.flush()`: without it, a batch containing the same id twice inserts it twice and violates the primary key on commit. Trailing-window re-scans overlap by design, so this is a normal input, not a defensive edge case.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_chat_store.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add api/chat_store.py tests/test_chat_store.py
git commit -m "💾 Upsert GroupMe messages so favorite counts stay current"
```

---

## Task 5: Poller job

**Files:**
- Create: `jobs/ingest_groupme.py`
- Test: `tests/test_ingest_groupme.py`

**Interfaces:**
- Consumes: `iter_messages` (Task 3), `upsert_messages` (Task 4), `record_job_run` from `jobs/sheets_ingestion_shared.py`.
- Produces: `INGEST_GROUPME_JOB_NAME = "ingest_groupme"`, `rescan_window_start(days=14) -> datetime`, `run(days=14) -> tuple[int, int]`.

- [ ] **Step 1: Write the failing test**

```python
"""The GroupMe poller re-scans a trailing window.

Favorite counts rise after a message posts, so a poller that fetches only
messages newer than its high-water mark freezes every count at whatever it was
seconds after posting. It re-reads a trailing window instead and lets the
upsert refresh what changed.
"""

import pytest

from api.models import ChatMessage, JobMeta
from jobs import ingest_groupme


@pytest.fixture
def job_db(db, monkeypatch):
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ingest_groupme, "SessionLocal", lambda: db)
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("GROUPME_READ_GROUP_ID", "g1")
    return db


def raw(mid, favs=0, created=1700000000):
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": ["x"] * favs, "created_at": created}


def test_run_persists_fetched_messages(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1"), raw("m2")]))
    inserted, updated = ingest_groupme.run()

    assert inserted == 2
    assert job_db.query(ChatMessage).count() == 2


def test_run_refreshes_favorite_counts_on_rescan(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", favs=1)]))
    ingest_groupme.run()

    monkeypatch.setattr(ingest_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m1", favs=9)]))
    inserted, updated = ingest_groupme.run()

    assert (inserted, updated) == (0, 1)
    assert job_db.query(ChatMessage).one().favorite_count == 9


def test_run_records_success_in_job_meta(job_db, monkeypatch):
    monkeypatch.setattr(ingest_groupme, "iter_messages", lambda *a, **k: iter([raw("m1")]))
    ingest_groupme.run()

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "success"
    assert meta.last_success_at is not None


def test_run_records_error_and_reraises(job_db, monkeypatch):
    def boom(*a, **k):
        raise ingest_groupme.GroupMeError("token rejected")

    monkeypatch.setattr(ingest_groupme, "iter_messages", boom)
    with pytest.raises(ingest_groupme.GroupMeError):
        ingest_groupme.run()

    meta = job_db.query(JobMeta).filter_by(
        job_name=ingest_groupme.INGEST_GROUPME_JOB_NAME).one()
    assert meta.status == "error"
    assert meta.last_success_at is None


def test_missing_credentials_is_a_clear_error(job_db, monkeypatch):
    monkeypatch.delenv("GROUPME_ACCESS_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="GROUPME_ACCESS_TOKEN"):
        ingest_groupme.run()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest_groupme.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jobs.ingest_groupme'`

- [ ] **Step 3: Write the poller**

```python
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
from api.groupme import GroupMeError, iter_messages
from api.models import ChatMessage
from jobs.sheets_ingestion_shared import record_job_run

INGEST_GROUPME_JOB_NAME = "ingest_groupme"
RESCAN_DAYS = 14


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
            for message in iter_messages(group_id, token):
                created = datetime.fromtimestamp(message["created_at"], tz=timezone.utc)
                if created < cutoff:
                    break
                batch.append(message)

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ingest_groupme.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add jobs/ingest_groupme.py tests/test_ingest_groupme.py
git commit -m "🔄 Poll GroupMe on a trailing window so favorite counts stay live"
```

---

## Task 6: Season backfill

**Files:**
- Create: `jobs/backfill_groupme.py`
- Test: `tests/test_backfill_groupme.py`

**Interfaces:**
- Consumes: `iter_messages` (Task 3), `upsert_messages` (Task 4).
- Produces: `backfill(since: datetime, max_pages: int = 500) -> int` returning total messages stored.

- [ ] **Step 1: Write the failing test**

```python
"""One-time walk back through GroupMe history.

The chat's membership tracks the surviving field (252 in week 1, 22 by week
14), so volume decays across the season and this is a smaller job than a
252-person chat implies. It still needs a hard page ceiling: paging backward
forever on an unexpected response shape is the failure mode that burns the
rate limit.
"""

from datetime import datetime, timezone

from api.models import ChatMessage
from jobs import backfill_groupme


def raw(mid, created):
    return {"id": mid, "group_id": "g1", "user_id": "u1", "name": "Someone",
            "sender_type": "user", "text": "hi", "system": False,
            "favorited_by": [], "created_at": created}


SEP_2025 = int(datetime(2025, 9, 1, tzinfo=timezone.utc).timestamp())
AUG_2025 = int(datetime(2025, 8, 1, tzinfo=timezone.utc).timestamp())


def test_backfill_stops_at_the_since_date(job_db, monkeypatch):
    monkeypatch.setattr(backfill_groupme, "iter_messages",
                        lambda *a, **k: iter([raw("m2", SEP_2025), raw("m1", AUG_2025)]))

    stored = backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc))

    assert stored == 1
    assert [r.message_id for r in job_db.query(ChatMessage).all()] == ["m2"]


def test_backfill_returns_zero_on_empty_history(job_db, monkeypatch):
    monkeypatch.setattr(backfill_groupme, "iter_messages", lambda *a, **k: iter([]))
    assert backfill_groupme.backfill(
        since=datetime(2025, 9, 1, tzinfo=timezone.utc)) == 0
```

Move the `job_db` fixture out of `tests/test_ingest_groupme.py` and into `tests/conftest.py` so both job tests share it. Delete the local copy from `tests/test_ingest_groupme.py` in the same step.

Both job modules do `from api.database import SessionLocal`, which binds the name into *their* namespace at import time. Patching `api.database.SessionLocal` therefore does not reach them, so the fixture patches each job module by name:

```python
@pytest.fixture
def job_db(db, monkeypatch):
    """A session the jobs will not close, with GroupMe credentials stubbed."""
    from jobs import backfill_groupme, ingest_groupme

    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ingest_groupme, "SessionLocal", lambda: db)
    monkeypatch.setattr(backfill_groupme, "SessionLocal", lambda: db)
    monkeypatch.setenv("GROUPME_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("GROUPME_READ_GROUP_ID", "g1")
    return db
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backfill_groupme.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'jobs.backfill_groupme'`

- [ ] **Step 3: Write the backfill**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backfill_groupme.py tests/test_ingest_groupme.py -q`
Expected: 7 passed (the shared fixture change must leave Task 5's tests green)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: all green. This is the repo's check command; there is no `make check`.

- [ ] **Step 6: Commit**

```bash
git add jobs/backfill_groupme.py tests/test_backfill_groupme.py tests/conftest.py
git commit -m "⏪ Backfill GroupMe history to the season start"
```

- [ ] **Step 7: Run the real backfill (needs Task 1 credentials)**

Run: `python jobs/backfill_groupme.py --since 2025-09-01`

Record the actual message count. The spec's sizing assumption is that volume decays with the surviving field; this is the number that confirms or refutes it, and GRPM-3's corpus quality depends on it.

---

## Definition of done

- [ ] Retention probe answered RETAINED, or the epic was stopped and the spec revised
- [ ] `python -m pytest tests/ -q` green
- [ ] `chat_messages` populated from a real backfill, with a recorded row count
- [ ] `job_meta` has an `ingest_groupme` row with `status = "success"`
- [ ] A spot check confirms system messages ("X removed Y from the group") landed with `is_system = true`
- [ ] No token in any committed file: `git log -p | grep -i "groupme.*token" ` shows only variable names

## Out of scope

Posting (GRPM-4), `WeekFeatures` (GRPM-2), the voice corpus query and prompt (GRPM-3), Railway cron configuration for the poller (GRPM-4, alongside the bot credentials).
