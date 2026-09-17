# Optimization backlog — week roll & attrition anchor

Deferred findings from the tri-review of `feature/week-roll-and-attrition-anchor`
(2026-09-17). Applied findings are not listed; these are the ones consciously
left for later, with enough context to pick up cold.

## Declined by the owner, recorded so it is not re-opened

- **A quorum threshold on the roll.** Two reviewers flagged that the roll fires
  on the *first* pick of the new week, so the lead column can be ~7 of 179 while
  the manager is still aggregating GroupMe — and that sample decides the whole
  grid's row order and every `% of week` denominator. A 25%-of-field threshold
  was offered and **declined**: a grid days behind the scoreboard was the bug
  being fixed. Mitigated instead by captioning the lead column with its own
  completeness (`app/main.py`). Revisit only if the caption proves insufficient.

## Worth doing, not urgent

- **Resolve the week once per script run.** `main()` derives the week twice from
  two independently-cached snapshots (`app/main.py` live-scores block vs
  `render_weekly_picks_chart`). Extracting `resolve_grid_week` removed the
  duplicated *rule*, but not the duplicated *derivation*: if the 60s TTL on
  `get_week_game_statuses` expires between the two, the scoreboard and grid are
  computed from different snapshots for one render. Self-healing, benign, and
  structurally the same shape as the bug this branch fixed. Fix: hoist
  `summary` / `started_weeks` / `week_statuses` to the top of `main()` and pass
  the three resolved weeks down. Also collapses `get_summary_data` from four
  calls per run to one.

- **`get_started_game_weeks` is derivable in Python.** It is a third query over
  the same `Game`/season rows that `get_week_game_statuses` already fetches:
  `sorted(w for w, s in statuses.items() if any(x != "pre" for x in s))`. Needs
  care because `get_attrition_series` depends on it via `_last_started_week`.
  (`get_completed_week_count` was already collapsed this way on this branch.)

- **A partially-ingested slate reads as "final".** `week_is_final` is satisfied
  by a week holding three finished Thursday rows and nothing else, because
  `not statuses` only excludes a week with zero rows in `games`. In practice
  `jobs/update_scores.py` ingests whole weeks, so the window is narrow (season
  start, a fixture re-fetch). A floor — `len(statuses) >= 12`, or a comparison
  against the week's expected fixture count — would close it for all three
  callers at once, since they now share the predicate.

- **A postponed-and-never-replayed game disables the roll for its week.**
  `api/score_providers.py` maps any unrecognised ESPN status to `pre`, and
  `finalize_stuck_games` only rescues games that already have scores. That week
  then never reads as final. Documented in `week_is_final`'s docstring; bounded
  (the grid loses the roll, not the season). No fix attempted.

- **The hover assertion got softer.** `tests/test_attrition.py` used to assert
  on `customdata` (structured) and now substring-matches rendered `hovertext`,
  so it is coupled to `<br>` placement and `:,` formatting. Plotly accepts a
  per-point `hovertemplate` array, so `customdata` could be kept with a sentinel
  row for the anchor if the structured assertion is wanted back.

## Out of scope for this branch — `start.sh` is owned by `chore/start-sh-cleanup`

- **`start.sh` logs the first ~8 characters of the database password.**
  `echo "  DATABASE_URL: ${DATABASE_URL:0:30}..."` — 30 characters is past
  `postgresql://postgres:` and into the password, written to Railway deploy logs
  on every container boot. Pre-existing. **Fix on the start.sh branch.**

- **`--client.showErrorDetails=none`.** Streamlit 1.50 defaults to `full`, and
  nothing in `.streamlit/config.toml` or `start.sh` overrides it, so any
  unguarded exception renders its traceback to pool members — and psycopg2's
  connection errors carry the production host and user. Every render path in
  `app/main.py` is now individually guarded, so this is defence in depth rather
  than an open hole, but it is the change that makes the class impossible.

- **`create_engine(DATABASE_URL, pool_pre_ping=True)`** in `api/database.py`.
  Railway's Postgres proxy drops idle connections and there is no `pool_pre_ping`
  or `pool_recycle`, so the first query on a stale pooled connection raises
  `OperationalError`. This is the most common trigger for the guarded paths above.
