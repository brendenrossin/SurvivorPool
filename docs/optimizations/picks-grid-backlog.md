# Picks grid — deferred findings

From the tri-persona review of `feature/picks-heatmap-redesign` (2026-09-04).
Applied findings are recorded in `docs/design/picks-grid-spec.md`; these were
deliberately not applied, with the reason for each.

## Product decisions, not defects

### The pre-season reveal
`resolve_current_week` falls back to `min(pick_weeks)` when no games have
started, so week 1's picks render before kickoff — an unplayed week, which sits
against the reason future weeks are hidden. Not a regression: the old stacked
bar had no clamp at all. The alternative is showing nothing until first kickoff.
**Kept deliberately; revisit before 2027.**

### The Thursday-kickoff reveal
`get_started_game_weeks` treats a week as started when *any* game in it is not
`pre`, so one Thursday night game promotes the whole week and publishes every
Sunday pick ~3 days early. This is the dominant case once the season is running,
and it is week-granularity by design. Per-game gating would mean returning the
set of teams whose own game has kicked off and skipping the rest for the current
week. **Needs an explicit accept/reject.**

### Survivor-aware counts
The grid counts every pick, including those of already-eliminated entrants who
keep filling in the sheet (2025 week 4: 237 picks, 171 alive). The denominator
wording was corrected to "picks", which is now accurate — but if the grid should
measure the *live* field, both the cell counts and the totals need to filter
through `pick_results.survived`. That changes what the grid means, so it is a
product call rather than a fix.

## Deferred to the UI overhaul branch

The spec already scopes `graveyard.py`, `team_of_doom.py` and `survivors.py` to
a follow-up branch. The review found the case for it is stronger than colour:

- **No caching in any widget module.** Every `@st.cache_*` in `app/` lives in
  `dashboard_data.py`. `live_scores.py`, `team_of_doom.py`, `survivors.py`,
  `graveyard.py` and `chaos_meter.py` each open a session and query on every
  script run, and `st.tabs` executes all four tab bodies every time.
- **`survivors.py` is an N+1.** One pick-history query per survivor plus one
  `Game` lookup per survivor — `2N + 2` round trips.
- **The grid's two widgets make this worse.** They are the first always-visible
  widgets in the main body, so each toggle is now a full script rerun that
  re-executes all of the above against free-tier Postgres.

Fix shape: give each widget a cached data function in `dashboard_data.py`
returning plain dicts, leaving `render_*` as view code. Collapse the survivors
loop into one joined query.

## Smaller, genuinely deferred

- **`get_summary_data` runs one query per week** (18 weeks = 18 round trips)
  where one `GROUP BY Pick.week, Pick.team_abbr` would do. Cached at 60s, so the
  blast radius is one cache miss per minute.
- **`week_games` is an uncached read in the render path**, against the CLAUDE.md
  rule that every database read is cached. It pulls whole ORM `Game` rows when
  five columns are used. Fix: a cached `get_week_team_status(season, week)`
  returning `{team: 'won'|'lost'|'pending'}`, which would also make the
  tie-handling logic unit-testable.
- **Theme tokens are forked.** `"Inter, system-ui"`, the hover label colours and
  the font sizes are now declared in both `picks_grid.py` and
  `mobile_plotly_config.py` — the white-on-white hover bug has now been fixed
  twice, in two places. Fix: extract shared tokens, or add a `'picks_grid'`
  entry to `CHART_CONFIGS` that omits `height`/`xaxis`/`yaxis`.
- **Mobile column crowding.** Columns grow all season with no window. On a 390px
  phone, 14 columns leave ~23px per cell while `"100%"` needs ~28px, so late
  season `% of week` labels collide. Fix: a trailing window (last 8 weeks) with
  the full season behind a control. Needs a real device check first.
- **History ink is hardcoded** `#52514e` rather than computed by `label_ink()`,
  so a caller passing a dark `background` gets dark text on dark muted fills.
  Latent — `main.py` passes the light surface. Note the softer grey is
  deliberate: computing it would darken history and cost the recede effect.
- **Ingestion does not validate team abbreviations** against
  `db/seed_team_map.json` despite CLAUDE.md saying it does, so a sheet typo
  renders as a grey `#666666` row instead of being flagged.
- **`get_player_data` returns every pick for the season with no week clamp**, so
  "Find a Survivor" exposes future picks — the leak the grid exists to prevent.
  Pre-existing and outside this branch, but it contradicts the rule.

## Consequences of moving the app to a dark surface

Measured on `feature/ui-scores-and-grid`, 2026-09-04, reproducible from
`db/seed_team_map.json` with `relative_luminance` / `mute_color`. The surface
decision was still open when these were taken.

### The current-week emphasis collapses for dark teams

The grid's whole purpose is to lead with the current week: current cells carry
true team colour, earlier weeks carry `mute_color(team, background)` at 26%.
That separation is bounded by the distance from the team's colour to the
surface, so on a dark surface a dark team has no room to recede into.

CIE76 ΔE between a team's true and muted colour:

| | light `#F8FAFC` | dark `#0B1220` |
|---|---|---|
| mean | 63.7 | 37.7 (−41%) |
| teams under ΔE 10 | 0 | **4** |
| CHI `#0B162A` | 70.8 | **3.5** |
| HOU `#03202F` | 67.2 | **6.1** |
| LV `#000000` | 75.1 | **7.8** |
| TEN `#0C2340` | 66.6 | **9.7** |

ΔE 3.5 is around the just-noticeable threshold for large patches. For those four
teams the grid would stop leading with the current week at all.

This is **not** a collision with the elimination encoding — that mutes on
saturation and stays orthogonal. It is a magnitude problem inside the lightness
axis.

**No fix has headroom except lifting the emphasised end.** Raising `HISTORY_MIX`
moves muted *toward* true (worse); lowering it pins muted to the surface (also
worse). Lifting the current week's fill — `lift_color()`-style, hue preserved —
is the only direction with room, and it reopens the locked spec's first rule
that the current week carries the *true* team colour. That is a product call,
not a fix, so it is recorded here rather than applied.

**If the app stays light, none of this applies** and the grid is already correct.

### Not deferred: `label_ink` was miscalibrated

Found in the same pass and **fixed on this branch**, because it is
surface-independent and wrong on the shipping light build. `label_ink`
thresholded relative luminance at `0.45`; the real crossover where dark ink
overtakes white is `0.1791`. Five teams sat under the 4.5:1 small-text floor —
CIN and DEN `#FB4F14` at 3.37:1, MIA `#008E97` at 3.95:1, CAR `#0085CA` at
4.03:1, LAC `#0080C6` at 4.28:1. It now picks whichever ink yields more
contrast.
