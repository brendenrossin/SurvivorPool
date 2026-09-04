# Plots & visual refresh — design spec

**Status:** design approved; implementation not started
**Branch:** `feature/ui-plots-overhaul` (based on `staging`)
**Companion:** `docs/design/picks-grid-spec.md` — the reasoning this spec extends
**Scope:** everything Session B is not covering. Explicitly NOT `app/live_scores.py`,
`app/picks_grid.py`, or the `render_weekly_picks_chart` / live-scores regions of
`app/main.py`.

---

## Why

The owner's brief: *"the players remaining could stand to have an upgrade instead of
the donut plot... and same with the dumbest picks and big balls picks maybe something
more modern than just a table? and same with the pool insights graphs... this looks
like an early 2000s website."*

Three things the codebase adds to that, found before designing:

1. **The donut is worse than it looks.** 2025 finished at **1 survivor of 252** — 19
   is who *entered* week 14, not who came out. A donut of 1:251 is a solid ring. The
   attrition curve has real shape and the donut throws it away.
2. **None of these modules cache their database reads,** and `st.tabs` executes all
   four tab bodies on every script run. `survivors.py` is a `2N + 2` N+1;
   `chaos_meter.py` issues three queries per week in a loop (42 round trips for 2025).
3. **103 emoji across five files**, in headings, labels and every table row.
4. **~190 lines across the four modules are dead** — zero call sites. Two would raise
   if reached: `render_weekly_chaos_summary` calls `calculate_chaos_score`, which does
   not exist.

## The measured constraint: dark surface vs. true team colour

The approved direction is **broadcast dark** (`#0B1220`) *and* **true team colour on
bars**, as in the picks grid. Those collide, and the picks-grid spec's own rule is
that contrast gets computed, not assumed. Measured against `#0B1220`:

**22 of 32 team colours fail WCAG 1.4.11's 3:1 floor for a graphic object.** The
failures include the bars that matter most — `GB #203731` at **1.47:1** is the #1
Team of Doom bar with 73 eliminations, and would be effectively invisible.

### Resolution: `lift_color()`

The mirror of the grid's `mute_color()`. Blend the fill up in HLS **lightness only**,
preserving hue and saturation, until it clears the target ratio on the surface.

Measured result: **all 32 teams clear 3:1**, minimum 3.01:1, hue preserved.
`GB #203731 → #3E6A5E` is still recognisably Packers green.

| Effect | Before | After |
|---|---|---|
| GB | `#203731` 1.47:1 | `#3E6A5E` 3.06:1 |
| CHI | `#0B162A` 1.04:1 | `#2F5EB4` 3.01:1 |
| LV | `#000000` 1.12:1 | `#616161` 3.02:1 |
| PIT | `#FFB612` 10.66:1 | unchanged |

**Two honest losses, accepted:** `LV` black cannot be rendered on black and becomes
grey; `CHI` navy lifts far enough to read as blue. Both are tail teams (1 elimination
each in 2025). Identity still comes from the row label.

**Collisions after lifting:** among the top 8 doom teams, 3 of 28 pairs fall under
CIE76 ΔE 20 — `LAR/BUF` at ΔE 0.6 are effectively identical. This is acceptable under
the same rule the grid established: *each row is one team, named on the left, with the
number in the row.* Colour is reinforcement, never the sole channel. If a future change
moves teams off their own labelled rows, this must be revisited.

---

## Architecture

| File | Change | DB access |
|---|---|---|
| `.streamlit/config.toml` | NEW — `base="dark"` | — |
| `app/theme.py` | NEW — tokens, `lift_color`, `GLOBAL_CSS` | none |
| `app/attrition.py` | NEW — sparkline + full curve figures | none |
| `app/meme_cards.py` | NEW — ranked card rendering | none |
| `app/dashboard_data.py` | + 4 cached functions; week clamp fix | all of it |
| `app/team_of_doom.py` | rewrite as view-only | none |
| `app/graveyard.py` | rewrite as view-only | none |
| `app/survivors.py` | rewrite as view-only | none |
| `app/chaos_meter.py` | rewrite as view-only | none |
| `app/main.py` | CSS → theme, KPI row, tab bodies, meme call | none |

### Why `base="dark"` in config rather than more CSS

`main.py`'s current CSS block is a wall of `!important` because it is fighting
Streamlit's light base. Setting the base makes Streamlit's own widgets — tabs,
dataframes, selectboxes — render dark natively, so those overrides get **deleted
rather than extended**.

### Why `theme.py` imports from `picks_grid` rather than copying

The backlog records that theme tokens are already forked between `picks_grid.py` and
`mobile_plotly_config.py`, and that the white-on-white hover bug was consequently
fixed twice in two places. `theme.py` imports `relative_luminance`, `label_ink` and
`mute_color` from `picks_grid` — one import line, no edit to Session B's file, and no
third fork. If Session B refactors that module, this is one import to repoint at
rebase.

Moving `GLOBAL_CSS` out of `main.py` also shrinks its CSS region from ~70 lines to
one. That is deliberate: it is the likeliest conflict with Session B.

### Data layer

Every widget module loses database access entirely. Signatures change from
`render_x(db, season)` to `render_x(season)`, so the four `SessionLocal()` blocks in
`main.py`'s Pool Insights tabs are deleted with them.

| Function | Replaces | Round trips |
|---|---|---|
| `get_attrition_series(season)` | `chaos_meter`'s per-week loop | **42 → 1** (2025) |
| `get_survivor_board(season, week)` | `survivors.py`'s N+1 | **2N+2 → 1** |
| `get_doom_teams(season)` | `team_of_doom`'s Python aggregation | 1 |
| `get_graveyard(season)` | `graveyard.py`'s query | 1 |

All `@st.cache_data(ttl=60)`, all closing their session in a `finally`, all returning
plain dicts and lists so the `render_*` functions are pure view code.

`get_attrition_series` is the shared spine — it feeds the KPI sparkline, the
Elimination Tracker's season chart, and the Survivors board's context line. One query
replaces three separate widgets' worth of counting.

### One semantic fix: doom attribution

`get_doom_teams` attributes each player to their **first** elimination
(`MIN(week)` per player), which is what `graveyard.py` already does. The current
`team_of_doom.py` counts *every* losing pick.

In 2025 these coincide exactly — GB is 73 both ways — because eliminated players stop
filling in the sheet, so their later rows are null picks that the inner join to `games`
drops. They are still not the same question, and the current code answers the wrong
one. A season where eliminated entrants keep picking would diverge.

---

## Components

### Players Remaining → attrition sparkline

The donut is deleted. The "Players Remaining" KPI card carries a sparkline beneath its
number. This frees the donut's half-width column, so **Find a Survivor becomes full
width**.

The 2025 series the design is tuned against:

```
W1 252 · W2 246 · W3 238 · W4 171 · W5 127 · W6 74 · W7 61
W8 60 · W9 39 · W10 32 · W11-13 21 · W14 19 → 1
```

Weeks 3–5 remove 164 of 252. Weeks 11–12 remove nobody. The curve is a cliff followed
by a plateau, which is the story the donut cannot tell.

### Meme stats → ranked cards

`#1` gets hero treatment (large margin numeral, matchup, victim count); ranks 2–5 are
compact rows.

**Big Balls must degrade gracefully.** Every 2025 game has `point_spread = NULL`, so
`was_underdog` is always false and the panel collapses to road wins with counts of 1.
The card therefore leads with matchup and week, and treats the underdog badge as
optional garnish rather than the headline.

### Pool Insights charts

- **Team of Doom** — horizontal ranked bars, lifted team colour, `label_ink`-computed
  labels. The 2025 distribution is radically top-heavy (73, 32, 28, 24, 23, 16, 12,
  then a tail of 1–8), so rank order carries the meaning and colour is identity only.
- **Graveyard** — eliminations-per-week bars. Drops `color_continuous_scale="Reds"`,
  which encoded magnitude twice: once as bar height, once as fill.
- **Survivors** — same treatment; drops the `"Greens"` gradient.
- **Elimination Tracker** — **the gauge is deleted.** It is the most dated object in
  the app. Replaced by a large numeral plus the attrition curve with the current week
  marked, reusing `attrition.py` rather than introducing a fifth chart idiom.

### Emoji: removed, not reduced

There are **103 emoji across the five files this branch touches**. They are a large
part of why the app reads as dated, and they fight the broadcast direction directly:
`### 💀 Team of Doom` cannot sit in the same design language as an oversized numeral
on a slate field.

The rule applied here:

- **No emoji in headings, section titles, metric labels, or as row decoration.**
  `⚰️ Graveyard Board` becomes `GRAVEYARD` — uppercase, letterspaced, in the muted
  ink token. `💀 {player}` in a table row becomes `{player}`; the section already
  says what these rows are.
- **Where an emoji encoded status, it becomes a colour-coded text badge**, not
  another glyph. `🐕` / `🛣️` on a Big Balls card become `UNDERDOG` / `ROAD`.
  `✅ Won` / `⏳ Pending` become a coloured dot plus the word.
- **Empty-state messages lose their leading emoji too** — the §7 messages are plain
  sentences.

Two reasons beyond taste. Screen readers announce every emoji by name, so a table
with a skull per row reads as "skull" 251 times. And emoji render with the platform's
own colours, which no amount of theming controls — a full-colour glyph is the one
thing on the page that ignores the token system entirely.

**Scope note:** this covers this branch's files only. Session B's live-scores and
picks-grid regions keep theirs, so the app will be briefly inconsistent between their
merge and this one. Worth raising with them at reconciliation rather than editing
their files here.

### Empty states

From the roadmap (*"Every empty state needs its own message"*). Load-bearing right
now: production is 2026 with 5 entrants, week 1, every game `pre`, so most of these
panels are empty **today**. Each names the specific precondition it is waiting on.

| Widget | Message names |
|---|---|
| Attrition sparkline | the curve starts once week 1 goes final |
| Team of Doom | nobody eliminated yet; fills in when a picked team loses |
| Graveyard | first headstone lands when a picked team loses a completed week |
| Elimination Tracker | week 1 hasn't finished; rates appear when a week goes final |
| Dumbest Picks | ranks the worst beatings once picks start losing |
| Big Balls | road and underdog wins land here after week 1 |

---

## Performance and rules

- `@st.fragment` on the two tabs carrying filter widgets (Graveyard, Team of Doom), so
  changing a filter stops re-running the whole page. This is the backlog's specific
  complaint that `st.tabs` executes all four bodies on every run.
- **Rule 3 (never render an unplayed week's picks):** `get_player_data` currently
  returns every pick for the season with no week clamp, so "Find a Survivor" exposes
  future picks — the exact leak the picks grid exists to prevent. Clamped here.
- **CLAUDE.md caching convention:** every database read cached with `ttl=60` and every
  session closed in a `finally`. The review found this violated across precisely the
  files this branch touches.
- **Mobile-first:** charts must survive a 390px viewport, verified on one.

## Dead code removed

Zero call sites, confirmed by grep across `app/` and `tests/`:

`render_memorial_wall`, `render_graveyard_timeline` (graveyard) ·
`render_doom_details` (team_of_doom) · `render_survivor_timeline`,
`get_eliminated_count` (survivors) · `render_chaos_explanation`,
`render_weekly_chaos_summary`, and the `calculate_chaos_score` call it makes to a
function that does not exist (chaos_meter).

`render_survivor_timeline` also calls `len()` on `get_eliminated_count`'s `int`
return — it would `TypeError` if anything reached it.

## Testing

Logic lives in pure functions so it is reachable without a Streamlit runtime, the same
approach that made `picks_grid` testable.

- `tests/test_theme.py` — `lift_color` holds the 3:1 floor for all 32 real team
  colours, preserves hue, is idempotent, and leaves already-passing colours untouched.
- `tests/test_attrition.py` — series shaping, the single-week case, the plateau case.
- `tests/test_dashboard_data.py` — doom ranking and tie-breaks, the `get_player_data`
  week clamp.

The existing 60 tests must stay green. Verified against 2025 (252 → 1, real
eliminations) and 2026 (5 entrants, all `pre`) before the PR.

## Integration

Merge order is #28 (landed) → Session B → this branch. Session B had not committed
when this was designed, so their live-scores card idiom could not be read. The agreed
approach is that this branch defines the tokens in `theme.py` and **reconciles at
rebase**, adapting their cards onto those tokens during conflict resolution.

Conflicts are expected in `app/main.py` and `app/dashboard_data.py`. Edits here are
kept regionally scoped — and `GLOBAL_CSS` is moved out of `main.py` specifically to
shrink the shared surface.

## Out of scope

- Session B's files, listed at the top.
- The backlog's remaining items: survivor-aware grid counts, the Thursday-kickoff
  reveal, the pre-season reveal, ingestion-side abbreviation validation. All are
  product calls or belong to other files.
