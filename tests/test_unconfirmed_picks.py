"""The unconfirmed-picks widget's copy and geometry.

Everything testable here is deliberately outside the Streamlit call: the view
is built as plain data, so what the widget says and how long its bars are can
be asserted without rendering anything.
"""

import pytest

from app.unconfirmed_picks import MANAGER, build_tally_view

COLORS = {"LAC": "#0080C6", "JAX": "#006778", "DET": "#0076B6", "PIT": "#FFB612"}


def view(unconfirmed, confirmed, teams, week=1):
    return build_tally_view(
        {"week": week, "unconfirmed": unconfirmed, "confirmed": confirmed,
         "teams": teams},
        COLORS)


def test_bars_are_scaled_against_the_biggest_team():
    v = view(46, 10, [("LAC", 22), ("JAX", 13), ("DET", 10), ("PIT", 1)])
    widths = {r["team"]: r["pct"] for r in v["rows"]}
    assert widths["LAC"] == 100.0
    assert widths["JAX"] == pytest.approx(100 * 13 / 22)
    assert widths["PIT"] == pytest.approx(100 * 1 / 22)


def test_rows_keep_the_order_they_were_given():
    v = view(46, 10, [("LAC", 22), ("JAX", 13), ("DET", 10), ("PIT", 1)])
    assert [r["team"] for r in v["rows"]] == ["LAC", "JAX", "DET", "PIT"]


def test_the_jab_fires_when_the_chat_is_ahead():
    v = view(46, 10, [("LAC", 22)])
    assert v["jab"] is True
    # Not `MANAGER in caption`: an empty MANAGER makes that vacuously true.
    assert MANAGER and MANAGER in v["caption"]
    assert "officially update picks" in v["caption"]


def test_the_jab_does_not_fire_when_the_manager_is_current():
    """A bit that fires on a false premise is worse than no bit."""
    v = view(10, 46, [("LAC", 6)])
    assert v["jab"] is False
    assert "officially update picks" not in v["caption"]


def test_the_jab_does_not_fire_on_a_tie():
    v = view(10, 10, [("LAC", 6)])
    assert v["jab"] is False


@pytest.mark.parametrize("unconfirmed,confirmed,teams", [
    (46, 10, [("LAC", 22)]),
    (10, 46, [("LAC", 6)]),
    (0, 0, []),
])
def test_copy_never_mentions_the_sheet(unconfirmed, confirmed, teams):
    """Nobody reading the dashboard knows what "the sheet" is. The widget talks
    about GroupMe and about picks being confirmed, and never about the
    spreadsheet behind them."""
    v = view(unconfirmed, confirmed, teams)
    words = " ".join([v["caption"], v["heading"], v["unconfirmed_label"],
                      v["confirmed_label"]]).lower()
    assert "sheet" not in words
    assert "spreadsheet" not in words


def test_every_state_says_the_picks_came_from_groupme():
    for v in (view(46, 10, [("LAC", 22)]), view(10, 46, [("LAC", 6)])):
        assert "groupme" in v["caption"].lower()


def test_an_empty_tally_is_marked_empty_and_makes_no_joke():
    v = view(0, 12, [])
    assert v["empty"] is True
    assert v["jab"] is False
    assert v["rows"] == []


def test_a_season_with_no_week_is_empty():
    v = build_tally_view(
        {"week": None, "unconfirmed": 0, "confirmed": 0, "teams": []}, COLORS)
    assert v["empty"] is True


def test_an_unknown_team_still_gets_a_usable_colour():
    """A team missing from the colour map must not blow up the row."""
    v = build_tally_view(
        {"week": 1, "unconfirmed": 1, "confirmed": 0, "teams": [("ZZZ", 1)]},
        COLORS)
    assert v["rows"][0]["color"].startswith("#")
