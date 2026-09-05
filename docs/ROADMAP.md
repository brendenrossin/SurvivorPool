# Roadmap

Active work. Tickets move to `docs/DELIVERED.md` once their PR merges.

Status flow: `Backlog` → `Pending` → `In Progress` → `Review` → `PR` → delivered.

This file tracks ticketed engineering work. `docs/survivor_pool_product_roadmap.md`
remains the prose strategy doc (open-source vs SaaS, phases, market notes) and is not
superseded by it.

---

## Epic: GroupMe recap bot
> After every game in a week goes final, a bot posts one tweet-length recap into the
> pool's GroupMe. First LLM dependency in the repo, and the first job that writes
> somewhere real people are reading.

Spec: [`docs/design/groupme-recap-spec.md`](design/groupme-recap-spec.md)

| ID | Ticket | Est. | Status | Spec |
|----|--------|------|--------|------|
| GRPM-1 | GroupMe read client, `chat_messages` table, poller + season backfill | 2d | **Review** | [spec](design/groupme-recap-spec.md) |
| GRPM-2 | `WeekFeatures` extraction + backtest harness (no LLM) | 1d | **Pending** | [spec](design/groupme-recap-spec.md) |
| GRPM-3 | Recap generation + model/prompt bake-off across five anchor weeks | 2d | **Pending** | [spec](design/groupme-recap-spec.md) |
| GRPM-4 | Post to the staging test group, dry-run off, soak | 1d | **Blocked** | [spec](design/groupme-recap-spec.md) |
| GRPM-5 | Production bot | 0.5d | **Backlog** | [spec](design/groupme-recap-spec.md) |

**GRPM-1 is code-complete but not verified against the live API.** Tasks 2-6 are
built, reviewed and merged-ready (347 tests). Task 1 — the credential step and the
retention probe — is still open, so these definition-of-done items remain unmet:

- [ ] Retention probe answered RETAINED (does GroupMe keep removed members' messages?)
- [ ] `chat_messages` populated from a real backfill, row count recorded
- [ ] `job_meta` carries an `ingest_groupme` success row
- [ ] A removal system message spot-checked with `is_system = true`
- [ ] **Header auth confirmed.** The client sends `X-Access-Token` and this has
      never touched the live API. If it 401s, reverting to a `token` query param
      is one line and the redaction layer still protects logs.

## Epic: Engineering debt found during GRPM-1
> Surfaced by review while building the GroupMe ingestion. None introduced by it.

| ID | Ticket | Est. | Status | Spec |
|----|--------|------|--------|------|
| DEBT-1 | Test sessions use `autoflush=True`; production uses `autoflush=False` | 0.5d | **Backlog** | — |
| DEBT-2 | Nothing compares `api/models.py` to `db/migrations.sql` | 0.5d | **Backlog** | — |
| DEBT-3 | `test_ingest_job_meta.py` reads `NFL_SEASON` from the developer's `.env` | 0.25d | **Backlog** | — |

- **DEBT-1** — every test in the repo runs under different flush semantics than
  production. This masked a real bug during GRPM-1: deleting a load-bearing
  `db.flush()` left the whole suite green. Fixing it means re-pointing a fixture
  ~330 tests share, so it wants its own ticket and its own soak.
- **DEBT-2** — tests build the schema from SQLAlchemy metadata on SQLite while
  production builds it from the `.sql` on Postgres, so a column or index added to
  one and not the other ships green. GRPM-1 adds a table whose two indexes exist
  only in the file the tests never read.
- **DEBT-3** — the test hardcodes season 2026 but ingestion reads `NFL_SEASON` from
  `.env`. It is red on any machine set to 2025 and green otherwise. The test should
  pin its own season instead of inheriting the developer's environment. Note the
  local `.env` is also stale: it says 2025 while both databases carry 2026 data.

**Dependencies**

- GRPM-1 and GRPM-2 are independent and can run in parallel. GRPM-2's *harness* needs
  GRPM-1's corpus to be meaningful, but `WeekFeatures` does not.
- GRPM-3 needs both GRPM-1 and GRPM-2.
- GRPM-4 needs GRPM-3, **and** is blocked on an out-of-repo prerequisite: the owner
  creating the test GroupMe group and both bots (real-chat bot and test-group bot).
  A `bot_id` is bound to its group at creation, which is what makes staging unable to
  reach the real chat.
- GRPM-5 needs GRPM-4 to have soaked.

**Open risk on GRPM-1.** Most of the 2025 chat was written by players Travis has since
removed from the group. The entire voice corpus depends on GroupMe retaining their
messages after removal. Verify this before building the backfill loop; if it fails,
GRPM-3's few-shot strategy needs rethinking and the spec's assumptions change.
