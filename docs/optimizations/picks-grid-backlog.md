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
