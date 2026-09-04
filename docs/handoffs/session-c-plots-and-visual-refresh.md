# Handoff — Session C: remaining plots + visual refresh

Paste everything below into a fresh Claude Code session.

---

You are picking up a branch on the SurvivorPool repo at
`/Users/brentrossin/Side_Projects/SurvivorPool`. **Run `/dev-workflow` from the
top for this ticket** — brainstorming included, and it matters more here than on
any other branch, because your ticket is the one with the least predetermined
design. Do not start writing components before the direction is agreed.

## Set up an isolated worktree first

Two other sessions are working this repo concurrently. Do not work in the main
checkout.

```bash
cd /Users/brentrossin/Side_Projects/SurvivorPool
git fetch origin
git worktree add -b feature/ui-plots-overhaul ../SurvivorPool-plots origin/feature/streamlit-upgrade
cd ../SurvivorPool-plots
```

You branch from `feature/streamlit-upgrade` (PR #28), **not** `staging`, because
your work depends on Streamlit 1.50 APIs not yet on staging. You are **third in
the merge order**, so you will rebase twice: once after #28 lands, once after
Session B's branch lands.

**CLEAN UP WHEN DONE — this is required:**
```bash
cd /Users/brentrossin/Side_Projects/SurvivorPool
git worktree remove ../SurvivorPool-plots
git worktree prune
```

Reuse the main venv by absolute path if you like:
`/Users/brentrossin/Side_Projects/SurvivorPool/.venv/bin/python` (Python 3.9,
Streamlit 1.50.0).

## What this app is

A Streamlit + PostgreSQL NFL survivor-pool dashboard on Railway. Players pick
one team per week; pick a loser and you are eliminated. Read `CLAUDE.md` first.

- **production** deploys from `main` → `https://nfl-survivor-2026.up.railway.app/`
- **staging** deploys from `staging`
- Branch flow is `feature/*` → `staging` → `main`. Never push to `main`.

## Getting real data locally

2026 is live but nearly empty (5 entrants, week 1, all games `pre`) — useless
for judging a redesign. 2025 is still in the same tables as history: 252
entrants collapsing to 19 survivors over 14 weeks, with real eliminations,
graveyard entries and meme stats. **Develop against 2025.**

`DATABASE_URL` in `.env` is the Railway-*internal* host and will not resolve
locally. Use the public one:

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/streamlit run app/main.py
```

That is the **production** database. Read-only. Never write to it.

Tests: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`

## The brief, in the owner's words

> "the players remaining could stand to have an upgrade instead of the donut
> plot... and same with the dumbest picks and big balls picks maybe something
> more modern than just a table? and same with the pool insights graphs... this
> looks like an early 2000s website and could be updated pretty easily I think
> just based on the UI alone"

So: **a coherent visual refresh of everything Session B is not covering.**

### In scope

1. **"Players Remaining" donut** (`main.py`, rendered via `render_mobile_chart(fig, 'donut')`).
   A donut for a two-part ratio is a weak use of space. The interesting story is
   *attrition over time* — 252 → 246 → 237 → 170 → 127 → 74 → … → 19 across 14
   weeks. Consider whether the KPI row should carry that shape instead.
2. **"Dumbest Picks" and "Big Balls" tables** (`render_meme_stats` in `main.py`).
   These are the app's personality and they render as bare dataframes. They
   deserve to look like the joke they are.
3. **Pool insights charts** — `app/graveyard.py`, `app/team_of_doom.py`,
   `app/survivors.py`, `app/chaos_meter.py`. All four inherit the same problem
   the picks grid was just fixed for: **30 teams encoded as 30 competing
   colours**, which stops being readable past about seven classes. See
   `docs/design/picks-grid-spec.md` for how that was reasoned about and
   resolved for the grid — reuse the thinking, not necessarily the form.
4. **The overall visual language** — the global CSS block near the top of
   `main.py`, the KPI cards, spacing, type scale. The app currently reads as
   Streamlit defaults with a light coat of paint.

### Explicitly not yours

`app/live_scores.py`, `app/picks_grid.py`, and the `render_weekly_picks_chart` +
live-scores regions of `app/main.py`. **Session B owns those** and is working in
parallel on a live-scores card rebuild and a grid/table consolidation. Editing
them will cause conflicts.

Since Session B is establishing the card idiom for live scores, **look at their
branch before you finalise your direction** so the app ends up with one visual
language rather than two:
`git log origin/feature/ui-scores-and-grid` once it exists.

## Performance work that belongs to you

This is not just cosmetics. A three-persona review found the widget modules you
are rewriting have a real problem, documented in
`docs/optimizations/picks-grid-backlog.md`:

- **None of them cache their database reads.** Every `@st.cache_*` in `app/`
  lives in `dashboard_data.py`. `live_scores.py`, `team_of_doom.py`,
  `survivors.py`, `graveyard.py` and `chaos_meter.py` each open a session and
  query on every script run.
- **`st.tabs` executes all four tab bodies on every run**, so this is not
  hypothetical.
- **`survivors.py` is an N+1** — one pick-history query per survivor plus one
  game lookup per survivor, `2N + 2` round trips, against free-tier Postgres.

Since you are rewriting these components anyway, move each one's data access
into a cached function in `dashboard_data.py` returning plain dicts/lists, and
leave the `render_*` functions as pure view code. Collapse the survivors loop
into a single joined query. `st.fragment` (Streamlit 1.33+, now available) is
also worth considering so widget interactions stop re-running the whole page.

## Rules you must not break

1. **Cache every database read** with `@st.cache_data(ttl=60)` and close every
   session in a `finally`. This is a CLAUDE.md convention and the review found
   it is being violated across exactly the files you are touching.
2. **Mobile-first.** This dashboard is read on phones during games. Charts must
   survive a 390px viewport.
3. **Never render picks for a week that has not kicked off** — the sheet holds
   future weeks' picks. If any component you touch surfaces per-week pick data,
   clamp it. Related known hole, fair game if you want it: `get_player_data`
   returns every pick for the season with no week clamp, so "Find a Survivor"
   currently exposes future picks.
4. **Do not touch Session B's files** (listed above).

## Integration

Merge order is fixed: **#28 (Streamlit upgrade) → Session B → you.** Rebase onto
`staging` after each lands. Base your PR on `staging`. Expect to resolve
conflicts in `app/main.py` and `app/dashboard_data.py` — both sessions add to
them. Keep your edits regionally scoped so those conflicts stay mechanical.

## Context worth reading

- `docs/design/picks-grid-spec.md` — how the 30-colour problem was reasoned
  about and solved for the grid, including a measured CIE76 analysis of team
  colour collisions and why label contrast is computed rather than assumed.
- `docs/optimizations/picks-grid-backlog.md` — the full review backlog.
- `CLAUDE.md` — deployment, caching, Railway environments.

## Definition of done

Tests pass, `/tri-review` run with no Critical/High findings outstanding, the
app verified against 2025 **and** checked on a phone-width viewport, a PR into
`staging`, and your worktree removed.
