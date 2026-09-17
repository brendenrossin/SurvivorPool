# How this pool actually runs

Process context that is not visible anywhere in the code or the database, and
that changes what the app is allowed to show. Recorded because a reasonable
reader of the codebase would infer the opposite.

## Picks are public before kickoff

The order of events each week:

1. **Entrants post their pick to a GroupMe.** Everyone in the pool sees it, as
   it is made.
2. **The manager aggregates** those messages into the Google Sheet.
3. **The ingestion job reads the sheet** into `picks` (`jobs/ingest_sheet.py`).

So by the time a pick reaches the database it has already been public for
hours or days. **The app cannot leak a pick that the pool has already
published to itself.**

### What this changes

`app/live_scores.py` sets `PICKS_ARE_PUBLIC = True`, which makes
`should_reveal_picks()` return True unconditionally. The scoreboard therefore
filters to picked teams and shows pick counts **before** a week kicks off,
rather than waiting for the first game.

Without that context, the pre-kickoff behaviour looks like a disclosure bug —
and it was treated as one. `build_scoreboard()` deliberately suppressed both
the counts *and* the filtering for an unplayed week, on the reasoning that
narrowing a 16-game slate to 3 games publishes the field's picks by omission
even with no numbers shown. That reasoning is sound; it just does not apply to
a pool whose picks were public first.

**The gate was kept, not deleted.** A pool that collects picks privately -
DMs to a commissioner, a form, a locked sheet - sets `PICKS_ARE_PUBLIC = False`
and the pre-kickoff protections come back intact, with their tests
(`TestShouldRevealPicks` in `tests/test_live_scores.py`, which pass the flag
explicitly for that reason).

### What it also changed, as of 2026-09-17

The **picks grid** used to stop at the last week that kicked off, on the grounds
that the sheet holds *future* weeks - week 6's picks sitting in the sheet during
week 2 - which is a different question from whether the current week's picks are
public. That distinction still stands, but the clamp was doing more than it
needed to: it also held the grid on a *settled* week for three days while the
scoreboard had already rolled, so the two halves of one page named different
weeks from Monday night to Thursday evening.

The grid now rolls forward one week - to the next week that actually has picks -
once the current week is final. It publishes that week's picks before kickoff,
for the same reason the scoreboard does: they have been public in the GroupMe for
hours already. Weeks beyond that stay hidden; the roll advances by one settled
week, not to the end of the sheet.

`resolve_current_week`, `resolve_scoreboard_week` and `resolve_display_week` now
live together in `app/week_resolution.py`. They were in two modules that cannot
import each other, each with a private copy of "is this week over?", which is how
they drifted apart in the first place. See `docs/design/picks-grid-spec.md`,
*Amendment 2026-09-17*.

**The gate is still a single switch.** `resolve_display_week` takes
`picks_are_public` alongside `should_reveal_picks`, so a pool that collects picks
privately gets the pre-kickoff protection back on *both* surfaces, not just the
scoreboard.

## Multi-league

This is the single-league version. If the app ever hosts leagues run by other
people, `PICKS_ARE_PUBLIC` becomes per-league configuration rather than a
module constant - a league that collects picks privately must not inherit this
one's answer.
