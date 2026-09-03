"""Dashboard counts must reflect one season, not all history.

Players persist across seasons, so any query that starts from the players
table has to be narrowed by the season's picks.
"""

from datetime import datetime, timezone

from api.models import Player, Pick, PickResult, Game
from app.dashboard_data import (
    count_season_entrants,
    count_season_survivors,
    find_season_players,
)


def test_entrants_excludes_prior_season_players(seeded_db):
    """A 2025-only player is not an entrant in 2026."""
    assert count_season_entrants(seeded_db, 2026) == 1
    assert count_season_entrants(seeded_db, 2025) == 2


def test_survivors_excludes_prior_season_players(seeded_db):
    """Survivor count is drawn from this season's entrants only."""
    assert count_season_survivors(seeded_db, 2026) == 1


def test_survivors_excludes_eliminated_players(seeded_db):
    """A player with a losing pick this season is not a survivor."""
    game = Game(
        game_id="2026-1-SF",
        season=2026,
        week=1,
        kickoff=datetime(2026, 9, 10, tzinfo=timezone.utc),
        home_team="SF",
        away_team="LAR",
        status="final",
    )
    seeded_db.add(game)

    pick = seeded_db.query(Pick).filter(Pick.season == 2026).one()
    seeded_db.add(PickResult(pick_id=pick.pick_id, game_id=game.game_id, survived=False))
    seeded_db.commit()

    assert count_season_survivors(seeded_db, 2026) == 0
    assert count_season_entrants(seeded_db, 2026) == 1


def test_search_is_scoped_to_season(seeded_db):
    """Searching in 2026 does not surface a player who last played in 2025."""
    assert find_season_players(seeded_db, 2026, "player") == ["Returning Player"]

    names_2025 = find_season_players(seeded_db, 2025, "")
    assert "Alumni Only 2025" in names_2025
    assert "Returning Player" in names_2025


def test_search_returns_no_duplicates_across_seasons(seeded_db):
    """A player with picks in many weeks appears once."""
    assert find_season_players(seeded_db, 2025, "Returning") == ["Returning Player"]
