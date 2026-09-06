# Handoff — GroupMe recap: from ingestion to something on the page

Paste the block at the bottom into a fresh Claude Code session.

**Goal:** get the recap work visible in the dashboard UI. GRPM-1 (ingestion) is
merged; everything downstream is unbuilt.

---

## Where things stand

| Ticket | State | Visible in UI? |
|---|---|---|
| GRPM-1 — GroupMe client, `chat_messages`, poller + backfill | **merged** (PR #34) | No — by design, touches no `app/` file |
| GRPM-2 — `WeekFeatures` extraction + backtest harness | backlog | No |
| GRPM-3 — recap generation + model/prompt bake-off | backlog | No |
| GRPM-4 — recap feed widget (`app/recap_feed.py`) | backlog | **Yes** |
| GRPM-6 — unconfirmed pick tally | backlog | **Yes** |

Also in flight: `feature/test-infra-debt` clears DEBT-1/2/3 and an advisory-lock
bug. Independent of this work; rebase if it lands first.

## Read these first, in this order

1. **`docs/design/groupme-recap-spec.md`** — the design and, more importantly,
   *why*. It records decisions that were reversed and the evidence that reversed
   them. Do not re-derive them.
2. **`docs/ROADMAP.md`** — ticket states and the debt epic.
3. **`docs/pool-process.md`** — how the pool actually runs.
4. `CLAUDE.md` — conventions, Railway environments, the season-rollover rule.

## Things that were settled the hard way

Re-litigating any of these wastes a session. Each was decided against evidence.

- **There is no pick-disclosure problem here.** Picks are public in the GroupMe
  from the moment they are posted. This was mistaken for a leak twice during
  design. `CLAUDE.md` warns about exactly that mistake.
- **The recap renders on the site; it does not post to GroupMe.** Generating
  stops being publishing, the system stays read-only end to end, and a bad
  recap can be deleted instead of being unsendable in a 284-person chat.
- **The bot performs the commissioner's *function* in the group's *register*.**
  The best-liked chat is reactive banter the bot can never do (it posts
  standalone); the only standalone poster is the commissioner, whose
  announcement voice the owner rejects. Neither half is imitable, which is
  *why* the corpus is voice-reference-only and never content to reuse.
- **The corpus is built from exchanges, not lines.** 53.8% of season messages
  are bare pick declarations; GroupMe's reply feature is used by 2.1% of
  messages, so adjacency is the only conversational structure there is. The
  season's most-liked message is meaningless alone and a complete bit with the
  three preceding non-pick messages attached.
- **No emojis, no political jabs, tweet length.** The humans do all three and
  get liked for it. The bot deliberately does not — few-shot would otherwise
  teach it those are rewarded.
- **The unconfirmed tally needs sender *uniqueness*, not sender *identity*.**
  The manager maps senders to entrants himself. Keying on `user_id` with
  last-declaration-wins is required so a switch does not count twice.

## Verified against the live API (2026-09-05)

- Removed members' messages **are retained** — the gate the epic rested on.
- Header auth (`X-Access-Token`) returns 200; query-param auth also works.
- Envelope keys match what the parser assumes.
- Credentials are already in `.env`: `GROUPME_ACCESS_TOKEN`,
  `GROUPME_READ_GROUP_ID` (group `24708586`, "NFL Survivor 2026", 284 members).

## Suggested order, fastest to pixels

The dependency chain to a *recap* is long (GRPM-2 → 3 → 4). The tally is short.

**0. Populate `chat_messages` first.** Nothing downstream has data without it.
   `python jobs/backfill_groupme.py --since 2025-09-01`
   Record the row count; the spec's sizing assumption has never been tested at
   full season scale.

**1. GRPM-6 — the unconfirmed tally.** Shortest path to something on screen: it
   needs ingestion (done) and a parser, and **no LLM at all**.
   `scripts/prototype_pick_parser.py` is a measured starting point — 74.2%
   capture, 0.98pt mean share error, top-5 exact, scored against the 2025 sheet.
   Every 2025 week has ground truth, so improvements get a measured
   before/after. This is the only part of the feature that can be hill-climbed.

**2. GRPM-2 → GRPM-3 → GRPM-4** — the recap itself. GRPM-3's bake-off runs five
   anchor weeks (14, 3, 5, 7, 11) across three models for about $0.10 total; the
   owner reads the output and picks.

## Placement on the page

`app/main.py` order: live scores (~:180) → picks grid (~:216) → player search
(~:221) → meme stats (~:224) → footer. **The feed goes after the picks grid and
before player search** — after the two things people come for, ahead of what
they scroll to. The owner was explicit about not disturbing the first two.

## Traps

- **`make check` does not exist.** The command is `python -m pytest tests/ -q`.
- **Tests run SQLite; production runs Postgres.** They diverge on advisory locks
  (a no-op on SQLite) and on timezone-aware datetimes — SQLite returns naive
  where Postgres returns aware. **GRPM-2's `build_voice_corpus(db, as_of)`
  filters `created_at < as_of` and will hit this in its first test.**
- **Four tests on this branch named behaviors they could not detect.** Prove
  every new test can fail: break the thing it protects, watch it go red, restore.
  Do not accept "it passes" as evidence.
- `DATABASE_PUBLIC_URL` in `.env` points at **production** (`ballast`). Staging
  is `mainline`, reachable via `railway variables --environment staging
  --service Postgres`. Check which one before running anything.
