"""The unconfirmed tally: which declarations count, and for whom.

The tally's number is what the widget leads with, so the rules that bound it -
the week window, sender dedup, and the per-team cutoff - are what these tests
protect. Each one is a rule the prototype in scripts/prototype_pick_parser.py
got wrong or did not have.

Sessions here are autoflush=False (see conftest), matching production, so rows
are flushed explicitly before anything queries them.
"""

from datetime import datetime, timedelta

import pytest

from api.models import ChatMessage, Game
from api.pick_tally import resolve_window, tally_unconfirmed

WEEK1_KICK = datetime(2026, 9, 10, 0, 20)
WEEK2_KICK = WEEK1_KICK + timedelta(days=7)


def add_game(db, season, week, kickoff, home, away):
    db.add(Game(game_id=f"{season}-{week}-{home}-{away}", season=season,
                week=week, kickoff=kickoff, home_team=home, away_team=away,
                status="pre"))


def say(db, sender, text, when, *, name=None, sender_type="user",
        is_system=False):
    db.add(ChatMessage(message_id=f"{sender}-{when.isoformat()}-{text}",
                       group_id="g1", sender_id=sender,
                       sender_name=name or sender, sender_type=sender_type,
                       text=text, favorite_count=0, is_system=is_system,
                       created_at=when))


@pytest.fixture
def two_weeks(db):
    """Two weeks of 2026 games: LAC/JAX in week 1, DEN/PHI in week 2."""
    add_game(db, 2026, 1, WEEK1_KICK, "LAC", "JAX")
    add_game(db, 2026, 2, WEEK2_KICK, "DEN", "PHI")
    db.flush()
    return db


def test_a_declaration_counts_for_its_week(two_weeks):
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(hours=2))
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {"LAC": 1}


def test_last_declaration_wins_so_a_switch_is_not_counted_twice(two_weeks):
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(days=2))
    say(two_weeks, "u1", "Jaguars", WEEK1_KICK - timedelta(hours=3))
    two_weeks.flush()
    tally = tally_unconfirmed(two_weeks, 2026, 1)
    assert tally == {"JAX": 1}, "a switch must count once, for the later team"


def test_last_weeks_declarations_do_not_leak_into_this_week(two_weeks):
    """The prototype had no lower bound, so every prior week's declaration was
    still live. By week 14 of 2025 that reported 239 picks against a sheet of
    19."""
    say(two_weeks, "u1", "Broncos", WEEK1_KICK - timedelta(hours=2))
    two_weeks.flush()
    # DEN plays in week 2, so only the window's lower bound can reject this.
    # With a team that plays week 1 only, the bye filter did the work and
    # removing the lower bound left this test green.
    assert tally_unconfirmed(two_weeks, 2026, 2) == {}


def test_a_declaration_after_its_team_kicked_off_does_not_count(db):
    """An entrant may switch until the team they picked plays - but not after.

    The week needs a second, later game or the window's own upper bound rejects
    the message and the per-team cutoff is never exercised. Deleting the cutoff
    used to leave this test green.
    """
    add_game(db, 2026, 1, WEEK1_KICK, "LAC", "JAX")
    add_game(db, 2026, 1, WEEK1_KICK + timedelta(days=1), "DEN", "PHI")
    db.flush()
    say(db, "u1", "Chargers", WEEK1_KICK + timedelta(hours=1))
    db.flush()
    assert tally_unconfirmed(db, 2026, 1) == {}


def test_a_switch_after_the_new_teams_kickoff_keeps_the_earlier_pick(db):
    add_game(db, 2026, 1, WEEK1_KICK, "LAC", "JAX")
    add_game(db, 2026, 1, WEEK1_KICK + timedelta(days=1), "DEN", "PHI")
    db.flush()
    say(db, "u1", "Broncos", WEEK1_KICK - timedelta(days=1))
    say(db, "u1", "Chargers", WEEK1_KICK + timedelta(hours=1))
    db.flush()
    assert tally_unconfirmed(db, 2026, 1) == {"DEN": 1}


def test_a_team_not_playing_that_week_is_not_a_valid_pick(two_weeks):
    """DEN plays in week 2. Declaring it during week 1 is talk, not a pick."""
    say(two_weeks, "u1", "Broncos", WEEK1_KICK - timedelta(hours=2))
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {}


def test_distinct_senders_each_contribute_one_pick(two_weeks):
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(hours=5))
    say(two_weeks, "u2", "Chargers", WEEK1_KICK - timedelta(hours=4))
    say(two_weeks, "u3", "Jaguars", WEEK1_KICK - timedelta(hours=3))
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {"LAC": 2, "JAX": 1}


def test_system_and_bot_messages_are_ignored(two_weeks):
    say(two_weeks, "sys", "Chargers", WEEK1_KICK - timedelta(hours=5),
        sender_type="system", is_system=True)
    say(two_weeks, "bot", "Jaguars", WEEK1_KICK - timedelta(hours=4),
        sender_type="bot")
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {}


def test_week_one_does_not_reach_back_into_a_previous_season(db):
    """The group is reused season to season. An unbounded week-1 window pulls
    last season's declarations into this season's opening tally."""
    add_game(db, 2025, 1, datetime(2025, 9, 5, 0, 20), "LAC", "JAX")
    add_game(db, 2026, 1, WEEK1_KICK, "LAC", "JAX")
    db.flush()
    say(db, "u1", "Chargers", datetime(2025, 9, 4, 12, 0))
    db.flush()
    assert tally_unconfirmed(db, 2026, 1) == {}


def test_resolve_window_starts_at_the_previous_weeks_last_kickoff(two_weeks):
    start, end = resolve_window(two_weeks, 2026, 2)
    assert start == WEEK1_KICK
    assert end == WEEK2_KICK


def test_resolve_window_is_none_for_a_week_with_no_games(two_weeks):
    assert resolve_window(two_weeks, 2026, 9) is None


def test_tally_is_empty_for_a_week_with_no_games(two_weeks):
    """A real declaration has to exist, or this asserts emptiness in a world
    where nothing could be non-empty and both guards can be deleted green."""
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(hours=2))
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 9) == {}


# --- which week the tally is about ----------------------------------------
#
# Not the same question the picks grid asks. The grid leads with the last week
# that kicked off; the tally is about the week people can still declare for.
# Resolved from game status rather than a clock, both because that is how
# app/dashboard_data.get_started_game_weeks already does it and because
# comparing a Python `now` against a kickoff raises TypeError on SQLite, where
# the column comes back naive.

from api.pick_tally import resolve_pick_week


def set_status(db, season, week, status):
    for game in db.query(Game).filter(Game.season == season,
                                      Game.week == week).all():
        game.status = status
    db.flush()


def test_pick_week_is_the_first_week_not_yet_played(two_weeks):
    assert resolve_pick_week(two_weeks, 2026) == 1


def test_pick_week_advances_once_a_week_is_fully_played(two_weeks):
    set_status(two_weeks, 2026, 1, "final")
    assert resolve_pick_week(two_weeks, 2026) == 2


def test_pick_week_stays_while_a_week_is_only_partly_played(db):
    """A week with games still to come is still being picked - you can declare
    for any team that has not taken the field."""
    add_game(db, 2026, 1, WEEK1_KICK, "LAC", "JAX")
    add_game(db, 2026, 1, WEEK1_KICK + timedelta(days=1), "DEN", "PHI")
    add_game(db, 2026, 2, WEEK2_KICK, "BUF", "MIA")
    db.flush()
    db.query(Game).filter(Game.game_id == "2026-1-LAC-JAX").one().status = "final"
    db.flush()
    assert resolve_pick_week(db, 2026) == 1


def test_pick_week_falls_back_to_the_last_week_once_the_season_is_over(two_weeks):
    set_status(two_weeks, 2026, 1, "final")
    set_status(two_weeks, 2026, 2, "final")
    assert resolve_pick_week(two_weeks, 2026) == 2


def test_pick_week_is_none_for_a_season_with_no_games(two_weeks):
    assert resolve_pick_week(two_weeks, 2099) is None


def test_senders_are_keyed_by_id_not_display_name(two_weeks):
    """GroupMe display names are neither unique nor stable. Two entrants can
    share one, so keying dedup on the name would silently merge them into a
    single pick."""
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(hours=5),
        name="Mike")
    say(two_weeks, "u2", "Jaguars", WEEK1_KICK - timedelta(hours=4),
        name="Mike")
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {"LAC": 1, "JAX": 1}


def test_one_sender_renaming_themselves_still_counts_once(two_weeks):
    say(two_weeks, "u1", "Chargers", WEEK1_KICK - timedelta(hours=5),
        name="Mike")
    say(two_weeks, "u1", "Jaguars", WEEK1_KICK - timedelta(hours=4),
        name="Michael")
    two_weeks.flush()
    assert tally_unconfirmed(two_weeks, 2026, 1) == {"JAX": 1}
