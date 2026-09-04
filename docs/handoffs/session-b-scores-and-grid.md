# Handoff — Session B: live scores rebuild + chart consolidation

Paste everything below into a fresh Claude Code session.

---

You are picking up a branch on the SurvivorPool repo at
`/Users/brentrossin/Side_Projects/SurvivorPool`. **Run `/dev-workflow` from the
top for this ticket** — brainstorming included. Do not skip to implementation:
the design here is genuinely undetermined and that is the point of your session.

## Set up an isolated worktree first

Two other sessions are working this repo concurrently. Do not work in the main
checkout.

```bash
cd /Users/brentrossin/Side_Projects/SurvivorPool
git fetch origin
git worktree add -b feature/ui-scores-and-grid ../SurvivorPool-scores origin/feature/streamlit-upgrade
cd ../SurvivorPool-scores
```

You branch from `feature/streamlit-upgrade` (PR #28), **not** from `staging`,
because your work depends on Streamlit 1.50 APIs that are not on staging yet.
That PR merges first; rebase onto `staging` before you open yours.

**CLEAN UP WHEN DONE — this is required:**
```bash
cd /Users/brentrossin/Side_Projects/SurvivorPool
git worktree remove ../SurvivorPool-scores
git worktree prune
```

Your worktree needs its own venv, or reuse the main one by absolute path:
`/Users/brentrossin/Side_Projects/SurvivorPool/.venv/bin/python` (Python 3.9,
already upgraded to Streamlit 1.50.0).

## What this app is

A Streamlit + PostgreSQL NFL survivor-pool dashboard on Railway. Players pick
one team per week; pick a loser and you are eliminated. Read `CLAUDE.md` first —
it carries the deployment, caching and season-rollover conventions and they are
load-bearing.

- **production** deploys from `main` → `https://nfl-survivor-2026.up.railway.app/`
- **staging** deploys from `staging` → `nfl-survivor-2026-staging.up.railway.app`
- Branch flow is `feature/*` → `staging` → `main`. Never push to `main`.
- production and staging have **separate Postgres instances**.

## Getting real data locally

2026 is live but nearly empty — 5 entrants, week 1, every game still `pre`. The
interesting data is 2025, still in the same tables as history (252 players, 14
weeks, the pool collapsing to 19 survivors).

`DATABASE_URL` in `.env` is the Railway-*internal* host and will not resolve
locally. Use the public one:

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/streamlit run app/main.py
```

That points at the **production** database. Keep it read-only. Never run a
write, a migration, or an ingestion job against it.

Tests: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
(60 pass on your base).

## Your two deliverables

### 1. Rebuild the live scores widget as cards

`app/live_scores.py` currently renders a flat text dump inside an expander:
kickoff time, line, "Picked by N players", repeated per game. The owner wants
something like the ESPN college-football scoreboard — a two-column grid of game
cards, each showing both teams, score, game state, and the line.

`st.container(border=True)` (Streamlit 1.29+, now available) gives you real
cards without hand-rolled CSS. Everything you need is already in the data; this
is a layout and hierarchy problem, not a data problem.

Keep the survivor-pool angle that makes this app's scoreboard different from
ESPN's: **how many entrants picked each team, and what happens to them.** That
is the reason anyone looks at this page.

### 2. Consolidate the picks grid and the breakdown table

`render_weekly_picks_chart` in `app/main.py` renders the team × week grid and,
directly below it, a "Week N Picks Breakdown" table showing the same numbers
again. The owner wants them consolidated.

The table is not purely redundant: it carries a ✅ / 💀 / 🕐 glyph per team for
won / lost / not-started. **The owner explicitly does not want those emoji
carried over.** Instead:

> "if a team is eliminated during this current week when the game ends we change
> and mute their colors so you can clearly see who's eliminated mid week"

**Design constraint you must resolve — this is the crux of the ticket.** The
grid *already* uses muted colour to mean "an earlier week" (`mute_color()`
blends 26% of the team colour toward the surface). If you also use muting to
mean "eliminated", the two collide and the grid loses its primary encoding. You
need a treatment for a busted current-week pick that is unmistakably distinct
from history-muting. Think desaturation plus a strike, a red rule, reduced
opacity with a hard border — brainstorm it, mock it, and get the owner's sign
off before building. Do not silently pick one.

The data you need is specified but not written: a cached
`get_week_team_status(season, week) -> {team: 'won'|'lost'|'pending'}` in
`app/dashboard_data.py`. `app/main.py` currently does this query inline and
uncached, which violates the CLAUDE.md caching rule — folding it into a cached
helper is part of your ticket. Note that **a tie counts as a loss** for survivor
purposes; the existing inline logic at the bottom of `render_weekly_picks_chart`
handles that and you must preserve it.

## Rules you must not break

1. **Never render picks for a week that has not kicked off.** The Google Sheet
   holds picks for future weeks from day one. `aggregate_picks()` in
   `app/picks_grid.py` is the single place this is enforced, and it has tests.
   Read `docs/design/picks-grid-spec.md` before touching the grid — the grid's
   design is settled and approved; do not reopen it. Your job is to add the
   elimination state and absorb the table, not to redesign the grid.
2. **Cache every database read** with `@st.cache_data(ttl=60)` in
   `dashboard_data.py`, and close every session in a `finally`.
3. **Mobile-first.** Known open issue: at 14 columns on a 390px phone the grid's
   `% of week` labels crowd. If you have a clean fix, take it; otherwise leave
   it in the backlog.
4. **Do not touch** `app/graveyard.py`, `app/team_of_doom.py`,
   `app/survivors.py`, `app/chaos_meter.py`, the meme-stats tables, or the
   global CSS block in `main.py`. **Session C owns those** and is working in
   parallel. Editing them will cause conflicts.

## Files you own vs. Session C

- **Yours:** `app/live_scores.py`, `app/picks_grid.py`, `app/dashboard_data.py`
  (additive only — append new functions, don't restructure existing ones), and
  the `render_weekly_picks_chart` + live-scores regions of `app/main.py`.
- **Session C's:** `app/graveyard.py`, `app/team_of_doom.py`,
  `app/survivors.py`, `app/chaos_meter.py`, the KPI/meme-stats regions and the
  CSS block of `app/main.py`.

`app/main.py` and `app/dashboard_data.py` are shared. Keep your edits tightly
scoped to your regions and append rather than reorganise, so the merge is clean.

## Integration

Merge order is fixed: **#28 (Streamlit upgrade) → yours → Session C's.** After
#28 merges to `staging`, rebase onto `staging` before opening your PR. Base your
PR on `staging`. Session C rebases on top of you.

## Context worth reading

- `docs/design/picks-grid-spec.md` — the grid's design, locked, with the
  reasoning for every decision.
- `docs/optimizations/picks-grid-backlog.md` — findings from a three-persona
  review, including the caching gaps and the mobile crowding issue.
- `CLAUDE.md` — deployment and Railway environment rules.
- PR #26 (the grid) and PR #28 (the upgrade) for recent history.

## Definition of done

Tests pass, `/tri-review` run with no Critical/High findings outstanding, the
app verified headless against both 2025 and 2026, a PR into `staging`, and your
worktree removed.
