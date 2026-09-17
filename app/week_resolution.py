"""Which week the page is on.

Three views need an answer and they are not the same answer, which is exactly
why they live together. They were previously spread across `picks_grid.py` and
`live_scores.py` - two modules that cannot import each other, because
`live_scores` pulls in Streamlit and the database layer while `picks_grid` is
deliberately dependency-free - so the shared "is this week over?" predicate was
copied into both, plus a third time into `dashboard_data.py`.

That drift is not hypothetical. The bug that produced this module was the
scoreboard and the grid naming different weeks for three days a week, because
each owned its own rule. Keeping the rules adjacent is the point: their
differences should be reviewable in one screen.
"""

from typing import Dict, Iterable, List, Optional


def week_is_final(statuses: Optional[List[str]]) -> bool:
    """A week is over when it has games and every one of them is final.

    The empty case is False in both directions: a week with no rows in `games`
    has not been played, and neither has one whose rows are all still `pre`.

    Note the vocabulary is `{pre, in, final}` and `api/score_providers.py` maps
    any unrecognised ESPN status to `pre`. A game that is postponed and never
    replayed therefore sits at `pre` forever and its week never reads as final.
    The cost is bounded - the roll below stops, the season does not.
    """
    return bool(statuses) and all(status == "final" for status in statuses)


def resolve_current_week(
    pick_weeks: Iterable[int], started_game_weeks: Iterable[int]
) -> int:
    """The last week that has actually kicked off.

    Picks are entered in the sheet weeks ahead of kickoff, so the latest week
    holding a pick is not "now". The current week is the latest week whose games
    have actually started, clamped to the weeks that have picks (the NFL
    schedule runs past the pool's final week).

    Args:
        pick_weeks: every week with at least one pick
        started_game_weeks: every week with at least one game underway or final

    Returns:
        The last week that kicked off; 1 before the season starts.
    """
    pick_weeks = list(pick_weeks)
    started = list(started_game_weeks)

    if not pick_weeks:
        return 1
    if not started:
        return min(pick_weeks)

    # The latest week that has picks *and* has kicked off. Taking
    # min(max(started), max(pick_weeks)) instead would return a week that has no
    # picks whenever the pick weeks have a gap - the grid would then bold a
    # column that isn't drawn and lead with no full-colour cell at all.
    kicked_off = max(started)
    eligible = [w for w in pick_weeks if w <= kicked_off]
    return max(eligible) if eligible else min(pick_weeks)


def resolve_scoreboard_week(
    current_week: int, week_statuses: Dict[int, List[str]]
) -> int:
    """The week the scoreboard should show.

    Rolls forward once a week is finished, so Tuesday shows the upcoming slate
    rather than a settled one. The roll is driven by whether the games actually
    finished. The rule this replaces added a week every Tuesday after 04:00 UTC
    whether or not anything had been played, on top of a base week derived as
    max(Game.week) - which in 2025 is week 16, a week nobody played, because the
    NFL schedule outruns the pool.
    """
    if not week_is_final(week_statuses.get(current_week)):
        return current_week
    following = current_week + 1
    return following if following in week_statuses else current_week


def resolve_display_week(
    current_week: int,
    week_statuses: Dict[int, List[str]],
    pick_weeks: Iterable[int],
    picks_are_public: bool = True,
) -> int:
    """The week the grid, its breakdown and its legend should lead with.

    `resolve_current_week` stops at the last week that *kicked off*. That left
    the grid sitting on a settled week from Monday night to Thursday evening
    while the scoreboard, on `resolve_scoreboard_week`, had already moved on:
    the two halves of one page named different weeks.

    This composes `resolve_scoreboard_week` rather than restating it - they must
    not drift - and adds the gate the scoreboard does not need. A scoreboard may
    show an empty upcoming slate; a picks grid whose newest column is blank is
    worse than one a few days behind. So the roll waits for picks.

    Showing a week before it is played publishes picks ahead of their games.
    That is deliberate and specific to this pool: entrants post picks to a
    GroupMe where everyone sees them and the manager aggregates them into the
    sheet afterwards, so by the time a pick reaches the database it has been
    public for hours. Same ruling as PICKS_ARE_PUBLIC on the scoreboard - and
    `picks_are_public` is threaded through here for the same reason the
    scoreboard's `should_reveal_picks` takes it: a pool that collects picks
    privately flips one constant and gets the pre-kickoff protection back on
    *both* surfaces. See docs/pool-process.md.

    Args:
        current_week: the week `resolve_current_week` landed on
        week_statuses: {week: [game status, ...]} for the season
        pick_weeks: every week that has a pick the grid would draw
        picks_are_public: when False, never lead with an unplayed week

    Returns:
        `current_week`, or the next week holding picks once everything up to it
        has finished.
    """
    if not picks_are_public:
        return current_week
    if not week_is_final(week_statuses.get(current_week)):
        return current_week

    # Step to the next week that actually has picks, not to current_week + 1.
    # The pool skips weeks (2025's sheet has gaps), and stepping blindly lands
    # on a week with nothing to draw, which re-creates the very disagreement
    # this function exists to remove: the grid holds while the scoreboard rolls.
    following = next((w for w in sorted(set(pick_weeks)) if w > current_week), None)
    if following is None or following not in week_statuses:
        return current_week

    # Every scheduled week we step over must itself be settled, or the roll
    # would jump past a week that is still being played.
    for skipped in range(current_week + 1, following):
        if skipped in week_statuses and not week_is_final(week_statuses[skipped]):
            return current_week

    return following


def resolve_grid_week(
    pick_weeks: Iterable[int],
    started_game_weeks: Iterable[int],
    week_statuses: Dict[int, List[str]],
    picks_are_public: bool = True,
) -> int:
    """The composition the dashboard actually calls.

    This exists as its own function because the composition is the part that
    can be silently deleted. The picks-grid spec records the same lesson from an
    earlier review: the future-week clamp lived in the Streamlit view function
    where no test could reach it, and removing it passed the whole suite.
    """
    return resolve_display_week(
        resolve_current_week(pick_weeks, started_game_weeks),
        week_statuses,
        pick_weeks,
        picks_are_public,
    )
