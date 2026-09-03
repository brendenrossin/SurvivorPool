# Weekly Picks Grid — design spec

**Status:** design approved, implementation ~60% done
**Branch:** `feature/picks-heatmap-redesign`
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
3. **Two concrete bugs.** `height: 300` is fixed and too short
   (`app/mobile_plotly_config.py:47`), and the hover label sets `bgcolor="white"`
   and `font_size` but never `font_color` (`:107`) — so Plotly keeps the
   auto-contrast ink it computed from the dark team fill and renders near-white
   text on a white background.

## What it becomes

A **team × week grid** that leads with the current week.

- **Rows** are teams, `max(10, teams picked this week)`, no upper cap.
- **Row order** is this week's pick count descending, then season total descending,
  then alphabetical. Rows beyond the current week's teams are filled by season total.
- **Columns** are weeks `1..current_week`. Future weeks are not shown.
- **The current week's cells** carry the true team colour.
- **Earlier weeks** carry a muted version of the team colour — blended 26% toward
  the surface — so history recedes but stays traceable by hue.
- **Every cell shows its number.** Because colour carries identity here rather than
  magnitude, the number is the only quantitative channel. Default is raw count, with
  a toggle for share of that week's survivors.
- **An expand toggle** drops the row limit and shows every team picked so far
  (up to 32 rows).

### Decisions, and why

| Decision | Choice | Reasoning |
|---|---|---|
| History style | **Muted team colour** | Keeps a team's run traceable across the row. Greyscale was the alternative — it would also encode magnitude by tone, but spends the emphasis contrast that makes the current week pop. |
| Number format | **Raw count**, `%` optional | Count is concrete ("14 people took DEN"). `%` stays available because the pool shrinks 252 → 19, which makes raw counts incomparable across weeks. |
| Future weeks | **Hidden** | The sheet holds picks for unplayed weeks from day one. Showing them would leak next week's picks. |
| Row cap | **None** | Realistically ≤16 teams in a week, usually far fewer. |
| Colour job | Identity, not magnitude | Follows from using team colours; forces the number into every cell. |

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

### Done (committed, 22 tests passing)

- **`app/picks_grid.py`** — new module:
  - `select_grid_rows(week_counts, season_totals, min_rows=10, expanded=False)`
  - `resolve_current_week(pick_weeks, started_game_weeks)`
  - `label_ink(hex)` / `relative_luminance(hex)` / `mute_color(hex, bg, amount)`
  - `build_picks_grid(...)` → `go.Figure`
- **`app/dashboard_data.py`** — added `get_started_game_weeks(season)`, cached 60s.
- **`tests/test_picks_grid.py`** — 22 tests over row selection, ordering,
  tie-breaking, padding, expansion, contrast, muting, and week resolution.

`app/main.py` is deliberately **untouched** — the new module is not yet wired in, so
the app still renders the old chart and nothing is half-migrated.

### Remaining

1. **Wire it into `main.py`.** Replace the 113-line block from
   `def render_weekly_picks_chart(summary):` through
   `render_mobile_chart(fig, 'bar_chart')`. Keep everything after it — the
   "current week picks breakdown" table below is part of the same function and
   still needed. Build the inputs from `summary["weeks"]`, `get_team_color_map()`
   and `load_team_data()`.
2. **Add the two Streamlit controls** — count/% and expand — as `st.radio`/
   `st.toggle` above the chart.
3. **Fix the shared hover config.** `app/mobile_plotly_config.py:107` needs an
   explicit `font_color`; this fixes the tooltip on *every* chart in the app, not
   just this one.
4. **Height.** The grid sets its own height (`len(rows) * 34 + 120`), so it must not
   be overwritten by `CHART_CONFIGS['bar_chart']['height']` in
   `apply_mobile_optimization`. Either pass a new chart type or have the grid skip
   mobile layout defaults.
5. **Verify against real data** — `PYTHONPATH=. streamlit run app/main.py` against
   the production read replica, checking week 1 (15 rows) and week 14 (3 picks
   padded to 10).

### Notes for whoever picks this up

- `tests/conftest.py` lives on `feature/season-rollover-2026` (PR #23), not here.
  These tests are pure functions and need no fixtures, so they run standalone —
  but after PR #23 merges, both test files share one directory.
- `requirements-dev.txt` (pytest) also arrives with PR #23.
- Run tests with `PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`.

## Out of scope

The same 30-colour problem exists in `app/graveyard.py`, `app/team_of_doom.py` and
`app/survivors.py`. Deliberately not touched — worth its own ticket.
