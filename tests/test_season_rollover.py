"""Season rollover safety.

Ingesting a new season must never destroy prior seasons' history.
"""

from api.models import Player, Pick
from jobs.sheets_ingestion_shared import clear_season_data


def test_clearing_new_season_preserves_prior_season(seeded_db):
    """Rolling into 2026 leaves every 2025 pick and player intact."""
    clear_season_data(seeded_db, season=2026)
    seeded_db.commit()

    picks_2025 = seeded_db.query(Pick).filter(Pick.season == 2025).all()
    assert len(picks_2025) == 3

    names = {p.display_name for p in seeded_db.query(Player).all()}
    assert "Alumni Only 2025" in names, "2025-only player was wrongly deleted"
    assert "Returning Player" in names


def test_clearing_removes_only_target_season_picks(seeded_db):
    """The target season's picks are cleared so ingestion can re-insert them."""
    clear_season_data(seeded_db, season=2026)
    seeded_db.commit()

    assert seeded_db.query(Pick).filter(Pick.season == 2026).count() == 0
    assert seeded_db.query(Pick).filter(Pick.season == 2025).count() == 3


def test_orphaned_players_are_removed(db):
    """A player with no picks in any season is cleaned up."""
    orphan = Player(display_name="Dropped Out")
    db.add(orphan)
    db.flush()
    db.add(Pick(player_id=orphan.player_id, season=2026, week=1, team_abbr="GB"))
    db.commit()

    clear_season_data(db, season=2026)
    db.commit()

    assert db.query(Player).filter(Player.display_name == "Dropped Out").count() == 0


def test_clearing_is_safe_on_empty_database(db):
    """No rows, no error."""
    clear_season_data(db, season=2026)
    db.commit()

    assert db.query(Player).count() == 0
