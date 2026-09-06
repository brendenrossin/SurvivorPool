"""Skip a sheet re-ingest when the sheet has not changed.

Hourly polling only makes sense if the 23 uneventful runs are cheap AND safe.
ingest_players_and_picks clears the whole season before re-inserting it, so
running it more often multiplies the window in which a partial read leaves the
season thin. The fingerprint is what keeps that window rare, not merely what
saves the work.

Sessions here are autoflush=False (see conftest), matching production.
"""

import pytest

from api.models import JobMeta, Pick, Player
from jobs.sheets_ingestion_shared import (
    fingerprint_job_name,
    ingest_is_unchanged,
    picks_fingerprint,
    read_fingerprint,
    store_fingerprint,
)

PICKS = {"Alice": {1: "DEN", 2: "PHI"}, "Bob": {1: "ARI"}}


def seed_picks(db, season=2026):
    player = Player(display_name="Alice")
    db.add(player)
    db.flush()
    db.add(Pick(player_id=player.player_id, season=season, week=1,
                team_abbr="DEN"))
    db.flush()


# --- the fingerprint itself -------------------------------------------------

def test_the_same_picks_fingerprint_the_same():
    assert picks_fingerprint(PICKS) == picks_fingerprint(dict(PICKS))


def test_key_order_does_not_change_the_fingerprint():
    """Sheet rows arrive in whatever order the API returns them. Order must not
    read as a change, or every poll re-ingests."""
    reordered = {"Bob": {1: "ARI"}, "Alice": {2: "PHI", 1: "DEN"}}
    assert picks_fingerprint(reordered) == picks_fingerprint(PICKS)


def test_a_changed_pick_changes_the_fingerprint():
    changed = {"Alice": {1: "DEN", 2: "KC"}, "Bob": {1: "ARI"}}
    assert picks_fingerprint(changed) != picks_fingerprint(PICKS)


def test_a_new_entrant_changes_the_fingerprint():
    added = dict(PICKS, Carol={1: "BUF"})
    assert picks_fingerprint(added) != picks_fingerprint(PICKS)


def test_a_removed_entrant_changes_the_fingerprint():
    assert picks_fingerprint({"Alice": PICKS["Alice"]}) != picks_fingerprint(PICKS)


def test_a_new_week_for_an_existing_entrant_changes_the_fingerprint():
    extended = {"Alice": {1: "DEN", 2: "PHI", 3: "SF"}, "Bob": {1: "ARI"}}
    assert picks_fingerprint(extended) != picks_fingerprint(PICKS)


# --- storage ----------------------------------------------------------------

def test_a_stored_fingerprint_reads_back(db):
    store_fingerprint(db, 2026, "abc123")
    assert read_fingerprint(db, 2026) == "abc123"


def test_reading_an_unseen_season_returns_none(db):
    assert read_fingerprint(db, 2026) is None


def test_storing_twice_overwrites_rather_than_duplicating(db):
    store_fingerprint(db, 2026, "first")
    store_fingerprint(db, 2026, "second")
    assert read_fingerprint(db, 2026) == "second"
    rows = db.query(JobMeta).filter(
        JobMeta.job_name == fingerprint_job_name(2026)).all()
    assert len(rows) == 1


def test_seasons_keep_separate_fingerprints(db):
    """Rolling the season must not make the new one look already-ingested."""
    store_fingerprint(db, 2025, "old-season")
    assert read_fingerprint(db, 2026) is None


# --- the skip decision ------------------------------------------------------

def test_unchanged_when_the_fingerprint_matches_and_picks_exist(db):
    seed_picks(db)
    store_fingerprint(db, 2026, picks_fingerprint(PICKS))
    assert ingest_is_unchanged(db, 2026, picks_fingerprint(PICKS)) is True


def test_changed_when_the_fingerprint_differs(db):
    seed_picks(db)
    store_fingerprint(db, 2026, "something-else")
    assert ingest_is_unchanged(db, 2026, picks_fingerprint(PICKS)) is False


def test_changed_when_no_fingerprint_has_ever_been_stored(db):
    seed_picks(db)
    assert ingest_is_unchanged(db, 2026, picks_fingerprint(PICKS)) is False


def test_an_empty_season_is_never_unchanged(db):
    """A wiped database with a surviving fingerprint row would otherwise skip
    forever the re-ingest that would repair it."""
    store_fingerprint(db, 2026, picks_fingerprint(PICKS))
    assert ingest_is_unchanged(db, 2026, picks_fingerprint(PICKS)) is False


def test_picks_from_another_season_do_not_count_as_this_seasons(db):
    seed_picks(db, season=2025)
    store_fingerprint(db, 2026, picks_fingerprint(PICKS))
    assert ingest_is_unchanged(db, 2026, picks_fingerprint(PICKS)) is False


# --- the skip, end to end ---------------------------------------------------
#
# The tests above cover the decision. These cover what the decision protects:
# ingest_players_and_picks clears the season before rebuilding it, so a skip
# that still cleared would be worse than no skip at all.

from jobs import sheets_ingestion_shared as shared
from jobs.sheets_ingestion_shared import (INGEST_JOB_NAME,
                                          ingest_players_and_picks)

SEASON = 2026


@pytest.fixture
def persistent_db(db, monkeypatch):
    """Point ingestion at the test session, keep it open, pin the season."""
    monkeypatch.setenv("NFL_SEASON", str(SEASON))
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(shared, "SessionLocal", lambda: db)
    return db


def picks_in(db, season=SEASON):
    return {(p.display_name, pick.week, pick.team_abbr)
            for pick, p in db.query(Pick, Player)
                             .filter(Pick.player_id == Player.player_id,
                                     Pick.season == season).all()}


def test_a_first_ingestion_runs_and_records_its_fingerprint(persistent_db):
    assert ingest_players_and_picks(PICKS) is True
    assert picks_in(persistent_db) == {
        ("Alice", 1, "DEN"), ("Alice", 2, "PHI"), ("Bob", 1, "ARI")}
    assert read_fingerprint(persistent_db, SEASON) == picks_fingerprint(PICKS)


def test_an_unchanged_second_run_leaves_the_picks_alone(persistent_db):
    """The failure this guards is not wasted work, it is data loss: a skip that
    still called clear_season_data would empty the season and not refill it."""
    ingest_players_and_picks(PICKS)
    before = picks_in(persistent_db)

    assert ingest_players_and_picks(PICKS) is True
    assert picks_in(persistent_db) == before
    assert before, "precondition: the first run must have ingested something"


def test_an_unchanged_run_says_it_skipped(persistent_db):
    ingest_players_and_picks(PICKS)
    ingest_players_and_picks(PICKS)

    row = persistent_db.query(JobMeta).filter(
        JobMeta.job_name == INGEST_JOB_NAME).first()
    assert row.status == "skipped"
    assert "unchanged" in row.message


def test_a_changed_sheet_is_re_ingested(persistent_db):
    ingest_players_and_picks(PICKS)
    changed = {"Alice": {1: "DEN", 2: "KC"}, "Bob": {1: "ARI"}}

    assert ingest_players_and_picks(changed) is True
    assert ("Alice", 2, "KC") in picks_in(persistent_db)
    assert ("Alice", 2, "PHI") not in picks_in(persistent_db)


def test_force_re_ingests_an_unchanged_sheet(persistent_db):
    """The escape hatch: --force must reach the rebuild, not just the log.

    Only SOME picks are removed, so the season is still non-empty and the
    fingerprint still matches - `ingest_is_unchanged` says True and `force` is
    the only thing that can cause the rebuild. Deleting every pick instead
    would let the empty-season guard do the work, and ignoring `force`
    completely would still pass.
    """
    ingest_players_and_picks(PICKS)
    bob = persistent_db.query(Player).filter(
        Player.display_name == "Bob").one()
    persistent_db.query(Pick).filter(Pick.player_id == bob.player_id).delete()
    persistent_db.commit()
    # The bulk delete does not sync the identity map, and this test loaded Bob
    # into it. Production opens a fresh session and loads players only after
    # clear_season_data, so the staleness is this test's, not the code's.
    persistent_db.expunge_all()
    assert ingest_is_unchanged(persistent_db, SEASON, picks_fingerprint(PICKS))

    assert ingest_players_and_picks(PICKS, force=True) is True
    assert picks_in(persistent_db) == {
        ("Alice", 1, "DEN"), ("Alice", 2, "PHI"), ("Bob", 1, "ARI")}


def test_without_force_an_unchanged_sheet_is_left_as_is(persistent_db):
    """The mirror of the test above: same starting state, no force, no repair.
    Together they pin `force` as the difference rather than something else."""
    ingest_players_and_picks(PICKS)
    bob = persistent_db.query(Player).filter(
        Player.display_name == "Bob").one()
    persistent_db.query(Pick).filter(Pick.player_id == bob.player_id).delete()
    persistent_db.commit()
    persistent_db.expunge_all()

    assert ingest_players_and_picks(PICKS) is True
    assert ("Bob", 1, "ARI") not in picks_in(persistent_db)


def test_an_emptied_season_re_ingests_without_force(persistent_db):
    """Fingerprint intact, picks gone - the run that repairs it must not be
    skipped just because the sheet has not changed."""
    ingest_players_and_picks(PICKS)
    persistent_db.query(Pick).filter(Pick.season == SEASON).delete()
    persistent_db.commit()

    assert ingest_players_and_picks(PICKS) is True
    assert len(picks_in(persistent_db)) == 3
