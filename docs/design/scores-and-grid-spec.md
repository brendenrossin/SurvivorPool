# Live scores cards + picks-grid consolidation — design spec

**Status:** design approved 2026-09-04; owner signed off on the elimination treatment
against the mock
**Branch:** `feature/ui-scores-and-grid` (from `staging` @ `06f61fc`)
**Mock:** https://claude.ai/code/artifact/28a2a8ec-694f-48eb-a8a0-8910ae0db17a
**Touches:** `app/live_scores.py`, `app/picks_grid.py`, `app/dashboard_data.py`,
and the two matching regions of `app/main.py`

Companion to `docs/design/picks-grid-spec.md`, which is **locked**. That spec's
design is not reopened here: muted team colour for history, raw count by default,
stop at the current week, no row cap, expand toggle. This spec adds one encoding
to the grid and deletes the table beneath it.

---

## Why

Two problems, both about the same week.

**The scoreboard is a text dump pointed at the wrong week.** `render_live_scores_widget`
prints kickoff, line and "Picked by N players" as stacked `st.caption` lines inside a
collapsed expander. It also derives its week as `max(Game.week)` — for 2025 that is
**week 16**, where all 16 games are still `pre`, because the NFL schedule outruns the
pool — and then adds one more on Tuesdays. So the scoreboard and the grid disagree
about what "this week" is, and the scoreboard's answer is a week nobody played.

**The grid and the table say the same thing twice.** `render_weekly_picks_chart` draws
the team × week grid and then, directly below it, a "Week N Picks Breakdown" table of
the same teams and the same counts in the same order. The table's only unique content
is a ✅ / 💀 / 🕐 glyph per team, which the owner does not want carried over.

## What the owner asked for

> "if a team is eliminated during this current week when the game ends we change and
> mute their colors so you can clearly see who's eliminated mid week"

## The design problem, and the resolution

The grid **already** uses muted colour to mean "an earlier week" — `mute_color()`
blends 26% of the team colour toward the surface. Muting a busted pick the same way
would collapse the grid's primary encoding into a gradient of one idea.

**Resolution: the two mutes move along different axes.**

| State | Fill | Axis |
|---|---|---|
| Earlier week | team colour blended toward the surface | drains **lightness**, keeps hue |
| Current week | true team colour | — |
| Busted this week | fully desaturated, luminance converged, 2px danger border | drains **hue**, keeps weight |

Desaturating *first* is what makes the border work. A red border on a team that is
already red — ARI, TB, SF — is invisible; on the converged grey it is the only
saturated thing in the cell. This is why "keep full colour, add a red cage" was
rejected.

The convergence is deliberate: every dead cell lands on roughly the same grey, because
elimination is a shared fate and identity already lives in the row label (see the
colour-tradeoff section of the locked spec).

### Verified on real data

Drawn on 2025 week 14 — 21 entrants alive, 16 of them on Tampa Bay, TB lost to NO,
20 eliminated in an afternoon. Ten rows, fourteen columns, true counts. The mock also
renders it at 390px and shows the three rejected candidates.

### Dark-surface interaction

Session C is taking the app to a dark surface (`#0B1220`). The axes argument is what
survives that change: history stays hue-bearing and low-lightness, elimination stays
hueless. Both the convergence target and the danger colour are **parameterised on
`background`**, exactly as `mute_color()` already is, so the token swap flows through
without revisiting this decision.

Three latent light-surface assumptions in `picks_grid.py` are fixed in the same pass,
because they are entangled with the new fill and cheaper to do once than to merge
twice:

- the cell border rule adds a hairline when `relative_luminance(fill) > 0.6`, so that
  light fills do not dissolve into the surface — on a dark surface it is *dark* fills
  that vanish. Becomes a contrast test against `background`.
- history ink is hardcoded `#52514e`; becomes computed from `background`.
- the hover label's colours are hardcoded light; become parameters.

### Decisions

| Question | Decision | Reasoning |
|---|---|---|
| Busted current-week cell | Desaturated fill, 2px danger border | Different axis from history; strike held in reserve, one boolean away |
| Winning current-week cell | No change — same as a game not yet kicked off | The scoreboard directly above answers game state in detail; the locked spec's first rule is that the current week reads as full team colour |
| Losing cells in earlier weeks | Untouched | Roughly half the board would be struck; history's job here is volume, not outcome |
| The breakdown table | **Deleted** | Its columns are team and count, both already in the grid, in the same order |
| ✅ 💀 🕐 glyphs | Gone with the table | Explicitly asked for |
| Legend | Added under the grid | The grid is gaining an encoding and has to name the three it now has |

---

## Deliverable 1 — live scores as cards

A two-column grid of `st.container(border=True)` cards, always visible (no expander),
in the position the widget occupies today.

**Built entirely from Streamlit 1.50 primitives with zero colour literals.**
`st.container(border=True, horizontal=..., gap=...)` and `st.badge(color=...)` are
theme-aware, so the cards follow `base="dark"` automatically and need no rebasing when
Session C lands the theme. No hand-rolled CSS, no team-colour fills, so no
`lift_color()` dependency.

### What a card carries

The survivor angle is the reason anyone opens this page rather than ESPN, so it is
the card's second line, not a footnote:

- **Status** — `🔴 LIVE` / `✅ FINAL` / kickoff in Pacific, per the CLAUDE.md chips
- **Both teams**, away then home, with score; the winner's row emphasised on a final
- **The line**, when the database has one (2025 has spreads on 31 of 240 games; 2026
  week 1 has all 16)
- **How many entrants are riding on each team**, as a badge on that team's row
- **What just happened to them** — on a final, the eliminated / survived split

### Which games

Picked-team games only, as today. In 2025 week 14 that is 4 cards of 14; in 2026
week 1 it is 3 of 16. Ordering is live games first, then kickoff time.

The exception is the rolled-forward week, below.

### Week resolution — two functions, deliberately not unified

The grid must keep leading with the last week that **kicked off**. The scoreboard
should roll forward once a week is over, per the roadmap:

> **Live scores should roll forward on Tuesday.** Once Monday's games are final, the
> widget should show the *next* week's games — still filtered to teams somebody has
> picked.

**The roadmap line as written leaks picks.** Filtering next week's games to teams
somebody picked publishes the field's picks days before kickoff, via the filter
itself — the exact leak `aggregate_picks()` exists to prevent, and the first rule of
this branch.

**Resolved with the owner:** roll forward, but a week that has not kicked off shows
the **full slate with no pick data at all** — no filtering, no counts, no badges. It
snaps back to picked-teams-only with counts the moment the week kicks off. The filter
is itself the leak, so it cannot apply pre-kickoff.

```
grid week       = resolve_current_week(pick_weeks, started_game_weeks)   # unchanged
scoreboard week = grid week, advanced by one when every game in it is final
```

Both the blind `max(Game.week)` derivation and the blind Tuesday `+1` are deleted.
The roll-forward is driven by whether the games actually finished, not by the day of
the week.

### Empty states

Per the roadmap item, each empty state says **why** it is empty, not that it is:

| Condition | Message |
|---|---|
| No games in the database for the week | schedule has not been ingested yet |
| Games exist, nobody has picked, week has kicked off | picks not imported yet, with the ingestion cadence |
| Week has not kicked off | full slate is showing; counts appear at kickoff |

---

## Deliverable 2 — grid absorbs the table

`render_weekly_picks_chart` keeps the grid and the two controls, gains a legend, and
loses the ~70-line breakdown-table block entirely, along with its inline `Game` query.

### New data function

The inline query violates the CLAUDE.md caching rule and is not reachable by a test.
It moves to `dashboard_data.py`:

```python
@st.cache_data(ttl=60)
def get_week_team_status(season: int, week: int) -> Dict[str, str]:
    """{team: 'won' | 'lost' | 'pending'} for one week."""
```

**A tie counts as a loss for both teams.** That rule is load-bearing for survivor
scoring and is preserved exactly as the inline code has it; it becomes unit-testable
for the first time. Only games that are `final` with both scores present are decided;
`pre` / `scheduled` are `pending`. Five columns are selected rather than whole ORM
rows.

### Grid changes

`build_picks_grid` takes a new optional `team_status` argument. When a current-week
cell's team is `'lost'`, the cell takes the busted treatment instead of the team
colour. Everything else — row selection, ordering, the future-week clamp, the count/%
toggle, the expand toggle, height — is untouched.

`team_status` defaults to `None`, so every existing test and caller renders exactly as
before.

---

## Testing

Pure functions, so the coverage sits in `tests/test_picks_grid.py` and
`tests/test_dashboard_data.py`:

- tie → both teams `'lost'`; decided game → winner `'won'`, loser `'lost'`;
  `pre`/`scheduled` → `'pending'`; `final` with a missing score → not decided
- desaturation: output is hueless (r == g == b); a light team and a dark team converge
  toward each other; the function is total over all 32 team colours
- the busted fill is not equal to `mute_color()` of the same team for any team colour,
  on both the light and the dark surface — the collision this design exists to prevent
- a `'lost'` team's **earlier** weeks are unaffected
- `team_status=None` produces the byte-identical figure it produces today
- scoreboard week: advances only when every game in the week is final; does not
  advance past the last week with games; falls back correctly pre-season
- a not-yet-kicked-off scoreboard week carries **zero** pick counts (the leak test)

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q` (60 on base).

Verified headless with `streamlit.testing.v1.AppTest` against 2025 and 2026, and
against the production database read-only.

## Out of scope

- `graveyard.py`, `team_of_doom.py`, `survivors.py`, `chaos_meter.py`, the meme-stats
  tables and the CSS block in `main.py` — **Session C owns these**
- The theme tokens themselves; this branch consumes them, Session C defines them
- Mobile column windowing (`docs/optimizations/picks-grid-backlog.md`) — the grid
  scrolling itself to the current week on load is noted there instead
- Survivor-aware counts, the Thursday-kickoff reveal, the pre-season reveal — all
  still open product calls in the backlog
