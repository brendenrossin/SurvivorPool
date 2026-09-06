# Optimization backlog — GRPM-6 unconfirmed pick tally

Deferred from tri-review. Nothing here blocks the ticket; the Critical/High
findings were fixed in `5d5ecae`.

## Deferred

| # | Severity | Where | Finding | Fix |
|---|---|---|---|---|
| 1 | Low | `app/unconfirmed_picks.py:_view_html` | `row["color"]` is interpolated into a `style` attribute unescaped. The value comes from `db/seed_team_map.json` through `contrast_fill`, which returns computed hex, so it is trusted today — but the escaping is positional, not guaranteed. | Validate against `^#[0-9a-fA-F]{6}$` before interpolating, or fall back. |
| 2 | Low | `app/dashboard_data.py:get_unconfirmed_tally` | Cache key is the season; the week is resolved *inside* the cached call. At a week rollover the widget can show the previous week for up to the 60s TTL. | Resolve the week outside and key the cache on `(season, week)`. |
| 3 | Low | `app/unconfirmed_picks.py` | `MAX_ROWS = 8` truncates the bar list, but the headline count is the full total, so bars need not sum to the headline. Invisible at today's 5 teams; visible in a wide-open week. | Add a "+N more" row, or note the truncation in the caption. |
| 4 | Low | `api/pick_tally.py:tally_unconfirmed` | Hydrates full `ChatMessage` ORM rows when three columns are used. Bounded by a week's traffic (~1.6k rows worst case in September), so not a live problem. | Project `sender_id, text, created_at` instead. |
| 5 | Nit | `app/unconfirmed_picks.py:_view_html` | The `<style>` block is re-emitted on every rerun, so the CSS accumulates in the DOM across reruns. | Hoist into `app/theme.GLOBAL_CSS`. |
| 6 | Nit | `scripts/score_pick_parser.py` | `r["share_error"] == r["share_error"]` as a NaN test is correct but obscure. | Use `math.isnan`. |

## Coverage gaps left in the parser, in measured order

Counted across 2025 over the 327 unparsed messages that contain a team token.
Ground truth exists for every week, so each gets a measured before/after.

| cluster | messages | note |
|---|---:|---|
| conversational (`Lions pls`, `LAC for me`, `Bills mafia`) | 226 | **Deliberately not chased.** `boys` is a Dallas token, so anything that catches these also turns "good luck boys" into a Dallas pick. |
| long / roster-ish (>60 chars) | 41 | overlaps the row below |
| roster posts (`Blake: Broncos Andrew: Philly …`) | 9 | needs a second code path: one message → several picks, keyed on the named person, and must not collapse under sender dedup |
| trailing emoji / parenthesised / `Paid` | — | **shipped** |
