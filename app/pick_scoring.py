"""How dumb a losing pick was.

Pure arithmetic, in its own module for the reason `app/week_resolution.py` is:
the ranking is domain logic, the cards are a view, and the data layer needs the
rank key. Putting the score in `meme_cards.py` made `dashboard_data` import a
view module, which dragged plotly into the data layer through
`meme_cards -> theme -> picks_grid`. Nothing here imports anything.
"""

from typing import Iterable, List, Optional

# A loss that beat the spread is still a loss, and if it took half the pool with
# it that is the story of the week. The floor keeps such a pick on the board
# instead of scoring it zero or negative and sorting it below a one-entrant one.
MIN_SHOCK = 1

MAX_DUMBEST = 5


def upset_shock(
    margin: float,
    point_spread: Optional[float],
    was_favorite: bool,
    favourite_known: bool = True,
) -> float:
    """How much worse the result was than the market expected, in points.

    A 10-point favourite losing by 12 is a 22-point swing; a 3-point underdog
    losing by 21 is only 18, because 3 of those points were priced in. Ranking
    on raw margin got this exactly backwards - it put a team that was *expected*
    to lose at the top of a list about dumb picks.

    Falls back to the raw margin when there is no usable spread, which is the
    common case rather than the edge: 2025 has odds for 31 of its 240 games, and
    a week's spreads only land once the odds job has run.

    `favourite_known` exists because `jobs/update_odds.py` writes `point_spread`
    and `favorite_team` in separate statements, each skipped if the new value is
    None. They are therefore not guaranteed to travel together, and a spread
    whose favourite is unrecorded must not be applied: `was_favorite` would be
    False by default and the code would confidently *subtract* the spread, as
    though the market had the team losing.
    """
    if point_spread is None or not favourite_known:
        return margin
    return margin + (point_spread if was_favorite else -point_spread)


def dumbness_score(
    margin: float,
    point_spread: Optional[float],
    was_favorite: bool,
    eliminated_count: int,
    favourite_known: bool = True,
) -> float:
    """Rank key: how wrong the pick was, times how many entrants it took.

    Owner's definition, chosen over ranking on either factor alone: a pick is
    dumb in proportion to how safe it looked and how much of the pool believed
    it. LAC in 2026 week 1 - a 10-point favourite that lost by 12 and ended 118
    of 300 entrants - is the case this is calibrated against.
    """
    shock = upset_shock(margin, point_spread, was_favorite, favourite_known)
    return max(shock, MIN_SHOCK) * eliminated_count


def shape_dumbest_pick(row, name_to_abbr):
    """Turn one query row into the dict the ranking and the cards both read.

    Pure and separate from the query so the name bridge is reachable by a test.
    That bridge is the single point where this feature silently reverts:
    `games.favorite_team` holds a full team name ("Los Angeles Chargers") while
    `picks.team_abbr` holds "LAC", so if the two stop lining up `was_favorite`
    is False for every team and every favourite gets its spread *subtracted* -
    strictly worse than ranking on raw margin, with nothing to show it broke.
    A review deleted the bridge and the whole suite stayed green.

    `name_to_abbr.get(name, name)` also tolerates a row that already stored an
    abbreviation, which older odds rows do.

    Args:
        row: a result row with week, team_abbr, home_team, away_team, margin,
             eliminated_count, point_spread and favorite_team
        name_to_abbr: {"Los Angeles Chargers": "LAC", ...}
    """
    opponent = row.away_team if row.team_abbr == row.home_team else row.home_team
    favourite_known = row.favorite_team is not None
    favourite = name_to_abbr.get(row.favorite_team, row.favorite_team)
    return {
        "week": row.week,
        "team": row.team_abbr,
        "opponent": opponent,
        "margin": row.margin,
        "eliminated_count": row.eliminated_count,
        "point_spread": row.point_spread,
        "favourite_known": favourite_known,
        "was_favorite": favourite_known and favourite == row.team_abbr,
    }


def unmapped_favourite_names(rows, name_to_abbr):
    """Favourite names the seed map does not know, for logging.

    An unmapped name is not an error - it scores as an underdog and the pick is
    quietly demoted about tenfold - so it has to be surfaced somewhere. The
    odds feed writes `favorite_team` verbatim from the provider, so a franchise
    rename upstream lands here first.
    """
    return sorted({
        row.favorite_team for row in rows
        if row.favorite_team is not None
        and row.favorite_team not in name_to_abbr
        and row.favorite_team not in name_to_abbr.values()
    })


def rank_dumbest_picks(picks: Iterable[dict], limit: int = MAX_DUMBEST) -> List[dict]:
    """Order losing picks worst-first and keep the top `limit`.

    The key is total on purpose. `sorted` is stable, so any component left out
    hands the remaining order back to whatever the database happened to return -
    and the query has no ORDER BY. That is not a hypothetical: 2025 has no
    spread for 209 of its 240 games and most weeks eliminate one entrant, so
    two teams losing by the same margin tie on score, count and margin alike.
    Without `week` and `team` the visible top five could reshuffle on every
    60-second cache refresh.

    Sorts ascending on negated numbers rather than passing `reverse=True`, so
    the numeric components can descend while the textual tiebreaks ascend.
    """
    return sorted(
        picks,
        key=lambda p: (
            -dumbness_score(
                p["margin"], p.get("point_spread"), p.get("was_favorite", False),
                p["eliminated_count"], p.get("favourite_known", True),
            ),
            -p["eliminated_count"],
            -p["margin"],
            p["week"],
            p["team"],
        ),
    )[:limit]
