# Weekly Picks Grid — design spec

**Status:** design approved and locked; built, wired into the dashboard, and verified
against both seasons
**Branch:** `feature/picks-heatmap-redesign` (current with `staging`)
**Mock:** `docs/design/picks-grid-mock.html` (also published as an artifact)
**Replaces:** the stacked bar chart in `app/main.py::render_weekly_picks_chart`

---

## Why

The current chart encodes 30 teams as 30 competing colours in a stacked bar. Three
things are wrong with it:

1. **Too many colour classes.** Past ~7, adjacent classes blur. The thin segments at
   the top of each bar are unreadable and unhoverable.
2. **The pool collapses.** Entrants go from **252 in week 1 to 19 in week 14**, so
   late weeks render as slivers a few pixels tall. The chart is effectively blank
   for the second half of the season.
3. **Two concrete bugs.** In `app/mobile_plotly_config.py`, the `bar_chart` entry
   of `CHART_CONFIGS` pins `'height': 300`, which is fixed and too short; and the
   `hoverlabel=dict(...)` in `apply_mobile_optimization` sets `bgcolor="white"` and
   `font_size` but never `font_color` — so Plotly keeps the auto-contrast ink it
   computed from the dark team fill and renders near-white text on white.

## What it becomes

A **team × week grid** that leads with the current week.

- **Rows** are teams, `max(10, teams picked this week)`, no upper cap.
- **Row order** is this week's pick count descending, then season total descending,
  then alphabetical. Rows beyond the current week's teams are filled by season total.
- **Columns** are weeks `1..current_week`. Future weeks are not shown.
- **The current week's cells** carry the team colour, lifted where it does not
  clear 3:1 against the surface (see *Amendment: the emphasis lift* below).
- **Earlier weeks** carry a muted version of the team colour — blended 26% toward
  the surface — so history recedes but stays traceable by hue.
- **Every cell shows its number.** Because colour carries identity here rather than
  magnitude, the number is the only quantitative channel. Default is raw count, with
  a toggle for share of that week's survivors.
- **An expand toggle** drops the row limit and shows every team picked so far
  (up to 32 rows).

### Amendment 2026-09-04: the emphasis lift

**This spec's first rule changed.** It said the current week carries the *true*
team colour; it now carries the team colour **lifted to clear WCAG 3:1 against
the surface**, via `contrast_fill()` in `app/picks_grid.py`. Owner-approved off a
rendered three-way comparison of the real 2025 week 6 grid, not off numbers.

**Why the original rule could not survive a dark surface.** The grid's emphasis
is the gap between the current week's fill and `mute_color()`, and that gap is
bounded by the distance from a team's colour to the surface. A dark team on
`#0B1220` has nowhere to recede to. CIE76 ΔE between a team's true and muted
colour:

| | light `#F8FAFC` | dark `#0B1220` |
|---|---|---|
| mean | 63.7 | 37.7 |
| teams under ΔE 10 | 0 | **4** |
| CHI `#0B162A` | 70.8 | **3.5** |
| HOU, LV, TEN | 67.2, 75.1, 66.6 | 6.1, 7.8, 9.7 |

ΔE 3.5 is around the just-noticeable threshold. For those teams the grid stopped
leading with the current week, which is its whole purpose. Against 2025's real
picks that is 23.8% of all picks at risk, including **GB — the second
most-picked team of the season, 116 picks — at ΔE 16.3 against light's 59.3.**

**Lifting the emphasised end is the only direction with headroom.** Raising
`HISTORY_MIX` moves muted *toward* true; lowering it pins muted to the surface.
Muting history toward `SURFACE_RAISED` was measured and is worse still (min ΔE
3.1, five teams under 10).

`contrast_fill` is **bidirectional** and hue-preserving, so it also *darkens*
PIT `#FFB612` and NO `#D3BC8D`, which fail against the light surface. A
lift-only version runs PIT to white.

**Accepted cost:** LV `#000000` has no hue to keep and lifts to a grey. Black
cannot be shown on black. Four picks in the whole 2025 season; reviewed
specifically before the ruling, and deliberately not special-cased back.

**History is not lifted**, and elimination is unaffected — it mutes on
saturation. Both are pinned by `TestLiftedGridKeepsBothMutingAxes`.

### Amendment 2026-09-04: the breakdown table is gone

The "Week N Picks Breakdown" table below the grid is deleted; the grid carries
win/loss itself. See `docs/design/scores-and-grid-spec.md`.

### Decisions, and why

| Decision | Choice | Reasoning |
|---|---|---|
| History style | **Muted team colour** | Keeps a team's run traceable across the row. Greyscale was the alternative — it would also encode magnitude by tone, but spends the emphasis contrast that makes the current week pop. |
| Number format | **Raw count**, `%` optional | Count is concrete ("14 people took DEN"). `%` stays available because the pool shrinks 252 → 19, which makes raw counts incomparable across weeks. |
| Future weeks | **Hidden** | The sheet holds picks for unplayed weeks from day one. Showing them would leak next week's picks. |
| Row cap | **None** | Realistically ≤16 teams in a week, usually far fewer. |
| Colour job | Identity, not magnitude | Follows from using team colours; forces the number into every cell. |
| Busted current-week pick | Desaturated fill, danger border | Mutes on *saturation*, so it cannot be read as history, which mutes on lightness. See `docs/design/scores-and-grid-spec.md`. |

### The team-colour tradeoff, measured

Every team pair that co-occurs in a week was run through CIE76. **54 pairs sit
under ΔE 20, and four are byte-identical:**

| Pair | Colour | Co-occur |
|---|---|---|
| CIN / DEN | `#FB4F14` | week 1 |
| DAL / LAR | `#003594` | weeks 2, 6 |
| NE / SEA | `#002244` | week 12 |

This is acceptable **only because identity comes from the row label**, not the fill.
Each row is one team, named on the left, with the number in every cell. Colour is
reinforcement and must never become the sole channel — if a future change moves
teams off their own rows, this decision has to be revisited.

Label ink is computed per cell from the fill's relative luminance (`label_ink()`),
never assumed: `PIT #FFB612` (0.55) and `NO #D3BC8D` (0.52) take dark ink;
`LV #000000` and `CHI #0B162A` take white. This is the same bug class as the
tooltip — contrast gets computed, not eyeballed. Light fills also take a hairline
border so they don't dissolve into the surface.

### Current week resolution

Picks are entered in the sheet **weeks ahead of kickoff**, so "the latest week with
a pick" is not *now* — in 2025 all 14 weeks were populated from day one. The grid
resolves the current week as:

```
min(latest week with a started game, latest week with picks)
```

falling back to week 1 before the season starts. The NFL schedule runs past the
pool's final week, which is why it clamps.

---

## Implementation status

### Done (55 tests passing)

- **`app/picks_grid.py`** — new module:
  - `select_grid_rows(week_counts, season_totals, min_rows=10, expanded=False)`
  - `resolve_current_week(pick_weeks, started_game_weeks)`
  - `label_ink(hex)` / `relative_luminance(hex)` / `mute_color(hex, bg, amount)`
  - `build_picks_grid(...)` → `go.Figure`
- **`app/dashboard_data.py`** — added `get_started_game_weeks(season)`, cached 60s.
- **`tests/test_picks_grid.py`** — 36 tests over row selection, ordering,
  tie-breaking, padding, expansion, contrast, muting, week resolution, the
  future-week clamp (`TestAggregatePicks`), cell fills and labels
  (`TestCellStyling`), and figure layout (`TestFigureLayout`).

- **`app/main.py`** — `render_weekly_picks_chart` now renders the grid; the 113-line
  stacked-bar block is gone, along with the `plotly.express` import it was the last
  user of.

### Remaining

All five steps are done.

1. ~~Wire it into `main.py`.~~ `render_weekly_picks_chart` now builds the grid's
   inputs from `summary["weeks"]`, clamped to the resolved current week. The
   "Week N Picks Breakdown" table below it is unchanged apart from sharing that
   resolved week (see below).
2. ~~The two Streamlit controls~~ — a `Count` / `% of week` radio and a
   "Show every team picked" toggle, in a two-column row above the grid.
3. ~~Fix the shared hover config.~~ `apply_mobile_optimization` now sets
   `font=dict(color="#0F172A", size=12)`; tooltips are legible app-wide.
4. ~~Height.~~ The grid is rendered with `st.plotly_chart(..., config=get_mobile_config())`
   rather than `render_mobile_chart`. `CHART_CONFIGS['bar_chart']` would have
   overwritten not just the height but the axis config the grid depends on
   (reversed y, array tickvals), so the grid skips the layout defaults entirely
   and keeps only the shared interaction config.
5. ~~Verify against real data.~~ Confirmed against the production database,
   read-only. See below.

#### Two things the wiring changed beyond the chart itself

- **The breakdown table shares the grid's week.** It used to derive its own week as
  `max(latest pick week, latest game week)`. For 2025 that is week 16 — the schedule
  outruns the pool's 14 weeks — so the table found no matching week and fell through
  to "No picks uploaded to Google Sheet Tracker yet". It now reads Week 14, and the
  table can no longer disagree with the column the grid highlights.
- **A closed session was being reused.** The table's game-status query ran on the
  session the week-derivation block had already closed in its `finally`. That block
  is gone; the query now opens and closes its own session.

#### Verified against the production database (read-only)

| Case | Result |
|---|---|
| 2025, current week 14 | 3 teams picked, padded to 10 rows, 14 columns, W14 bolded |
| 2025, current week 1 (simulated) | 15 rows, no cap applied |
| 2025, current week 3 (simulated) | 9 teams padded to 10 |
| 2026 live | 5 entrants, no started games → falls back to week 1 |
| Future-week leakage | 0 cells past the current week in every case |
| Height | `len(rows) * 34 + 120` in every case; shapes == annotations == drawn cells |

The whole app also runs clean headless via `streamlit.testing.v1.AppTest` against
both seasons, with both controls flipped.

#### Tri-review changes

A three-persona review ran before the PR. What it changed, beyond the wiring:

- **`aggregate_picks()` moved into `picks_grid.py`.** All three reviewers
  independently flagged that the future-week clamp — the rule this whole design
  rests on — lived in the Streamlit view function where no test could reach it.
  Deleting the clamp used to pass the entire suite. It is now a pure function
  with its own tests, including one asserting a future-only team cannot arrive
  as a padded row.
- **The denominator is "picks", not "survivors".** Eliminated entrants keep
  filling in the sheet: 2025 week 4 has 237 picks from 171 still-alive players.
  `week_totals` was the sum of picks while the tooltip called it survivors, so
  every `% of week` share was understated (a 20-pick team read 8.4% instead of
  11.7%). The wording now matches the arithmetic. Making the *numbers* survivor-
  aware is a real change to what the grid measures and is on the roadmap.
- **`resolve_current_week` could return a week with no picks.**
  `min(max(started), max(pick_weeks))` is only bounded by the pick weeks, not a
  member of them: `pick_weeks=[1,3]`, `started=[1,2]` returned 2. It now takes
  the latest pick week at or before kickoff.
- **`autorange="reversed"` was silently discarding the explicit y `range`**
  beside it, so row padding came from the invisible hover markers rather than
  the half-cell geometry the code stated.
- **`"{:.0f}%"` rendered a real pick as `0%`** — one picker out of 252 is 0.4%.
  Now `<1%`.
- **Columns are `1..current_week`,** per this spec. They were the weeks that
  *have* picks, which silently closed gaps and put W1 next to W3.
- **Failures in the breakdown table are logged and named.** Every exception —
  database outage included — was reported to the user as "No picks uploaded to
  Google Sheet Tracker yet", with nothing in the Railway logs.

Two findings were escalated rather than applied, because they change the
product rather than the code: the pre-season fallback (below) and the
Thursday-kickoff reveal, where one Thursday game promotes the whole week and
publishes Sunday's picks ~3 days early. Both are recorded in the backlog.

One correction to this spec's own expectation: 2026 renders **3 rows, not 10**.
`select_grid_rows` pads from teams picked in *earlier* weeks, and in 2026 every
team picked is in the current week, so there is nothing to pad with. Padding needs
history; it is exercised properly by 2025.

### Notes for whoever picks this up

- Run tests with `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`.
  55 pass on this branch: 36 for the grid, 19 inherited from `staging`.
- `tests/conftest.py` and `requirements-dev.txt` are already here — they merged in
  with the season-rollover work. The grid's own tests are pure functions and need
  no fixtures.
- The design is **settled**. Don't reopen it: muted team colour for history, raw
  count by default with a `%` toggle, stop at the current week, no row cap, and an
  expand toggle for every team picked so far. Build what the spec says.

### Testing against real data, post-rollover

The database rolled over to 2026 on 2026-09-04, which changes what live data can
show you:

- **2026 is nearly empty** — 5 entrants, week 1 only, every game still `pre`. That
  exercises row padding (3 teams padded to 10 rows) and the pre-season branch of
  `resolve_current_week` (no started games → falls back to `min(pick_weeks)`), but
  nothing else.
- **2025 is still in the database as history** — 1,612 picks, 252 players, 14 weeks.
  Point `NFL_SEASON=2025` at a local run to exercise the interesting cases: week 1's
  15 rows, and the late-season collapse to 3 picks that motivated this redesign.

Both seasons live in the same tables; the season lives on `picks`. See the
"Rolling to a new season" section of `CLAUDE.md`.

### Known, accepted: the pre-season reveal

Before any game has started, `resolve_current_week` falls back to
`min(pick_weeks)` and the grid renders week 1 — an unplayed week — which sits
awkwardly beside the decision table's reason for hiding future weeks. It is not
a regression (the old stacked bar showed every week with no clamp at all), and
the alternative is rendering nothing until first kickoff. Flagged, deliberately
kept, revisit before the 2027 season.

## Out of scope

The same 30-colour problem exists in `app/graveyard.py`, `app/team_of_doom.py` and
`app/survivors.py`. Deliberately not touched — a broader UI overhaul of the other
plots and tables is planned as its own follow-up branch, and folding it in here
would make this change impossible to review or revert cleanly.

The one exception is step 3 above: the `mobile_plotly_config.py` hover fix is a
single line that repairs tooltips app-wide. It ships here because the grid needs
it anyway and leaving it broken elsewhere would be gratuitous.
