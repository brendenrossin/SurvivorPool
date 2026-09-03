"""Row selection and cell styling for the weekly picks grid.

The grid leads with the current week: rows are the teams picked that week,
ordered by that week's count, padded out with the season's most-picked teams.
"""

import pytest

from app.picks_grid import (
    label_ink,
    mute_color,
    resolve_current_week,
    select_grid_rows,
)

SEASON_TOTALS = {"DEN": 132, "GB": 116, "BUF": 113, "ARI": 110, "BAL": 99,
                 "LAR": 98, "DET": 98, "SEA": 74, "KC": 40, "TB": 30,
                 "NE": 22, "SF": 20}


def test_current_week_teams_come_first_ordered_by_this_week():
    """This week's ordering wins over season totals."""
    rows = select_grid_rows({"SF": 9, "DEN": 3, "TB": 5}, SEASON_TOTALS, min_rows=10)
    assert rows[:3] == ["SF", "TB", "DEN"]


def test_padding_uses_season_totals_in_order():
    """Remaining slots go to the most-picked teams of the season."""
    rows = select_grid_rows({"SF": 9}, SEASON_TOTALS, min_rows=10)
    assert rows[0] == "SF"
    # LAR and DET both total 98 - the tie breaks alphabetically
    assert rows[1:] == ["DEN", "GB", "BUF", "ARI", "BAL", "DET", "LAR", "SEA", "KC"]


def test_no_duplicate_rows_when_padding():
    """A team picked this week is never repeated by the padding."""
    rows = select_grid_rows({"DEN": 4, "GB": 2}, SEASON_TOTALS, min_rows=10)
    assert len(rows) == len(set(rows))


def test_grows_past_the_minimum_when_many_teams_picked():
    """No row cap - a 12-team week shows 12 rows."""
    counts = {t: 1 for t in list(SEASON_TOTALS)[:12]}
    assert len(select_grid_rows(counts, SEASON_TOTALS, min_rows=10)) == 12


def test_pads_to_the_minimum_in_a_quiet_week():
    """Week 14 had 3 teams; the grid still shows 10 rows."""
    assert len(select_grid_rows({"TB": 8, "KC": 6, "SF": 5}, SEASON_TOTALS, min_rows=10)) == 10


def test_ties_this_week_break_on_season_total():
    """Equal counts this week fall back to who is bigger overall."""
    rows = select_grid_rows({"SF": 5, "DEN": 5}, SEASON_TOTALS, min_rows=2)
    assert rows == ["DEN", "SF"]


def test_ordering_is_deterministic_for_full_ties():
    """Identical counts and totals still produce a stable order."""
    totals = {"AAA": 10, "BBB": 10}
    assert select_grid_rows({"AAA": 3, "BBB": 3}, totals, min_rows=2) == ["AAA", "BBB"]


def test_handles_a_week_with_no_picks():
    """An unplayed week still renders the season's top teams."""
    assert select_grid_rows({}, SEASON_TOTALS, min_rows=10) == [
        "DEN", "GB", "BUF", "ARI", "BAL", "DET", "LAR", "SEA", "KC", "TB"]


def test_expanded_shows_every_team_picked_so_far():
    """The expand toggle drops the row limit entirely."""
    rows = select_grid_rows({"SF": 9}, SEASON_TOTALS, min_rows=10, expanded=True)
    assert len(rows) == len(SEASON_TOTALS)
    assert set(rows) == set(SEASON_TOTALS)


def test_expanded_keeps_the_current_week_on_top():
    """Expanding must not change which rows lead."""
    rows = select_grid_rows({"SF": 9, "TB": 2}, SEASON_TOTALS, min_rows=10, expanded=True)
    assert rows[:2] == ["SF", "TB"]


@pytest.mark.parametrize("hex_color,expected_dark", [
    ("#FFB612", True),   # PIT gold       - luminance .55
    ("#D3BC8D", True),   # NO  vegas gold - luminance .52
    ("#000000", False),  # LV  black
    ("#0B162A", False),  # CHI navy
    ("#FB4F14", False),  # DEN orange     - luminance .26
])
def test_label_ink_contrasts_with_the_fill(hex_color, expected_dark):
    """Ink is computed from luminance, never assumed."""
    assert (label_ink(hex_color) == "#0b0b0b") is expected_dark


def test_muting_moves_every_channel_toward_the_background():
    """A muted fill sits between the team colour and the surface."""
    team, bg = "#FB4F14", "#ffffff"
    muted = mute_color(team, bg, 0.26)
    for i in (1, 3, 5):
        orig, new, back = (int(c[i:i + 2], 16) for c in (team, muted, bg))
        assert abs(new - back) < abs(orig - back) or orig == back


def test_muting_is_stable_and_returns_a_hex_triplet():
    assert mute_color("#000000", "#ffffff", 0.0) == "#ffffff"
    assert mute_color("#000000", "#ffffff", 1.0) == "#000000"


class TestResolveCurrentWeek:
    """Picks are entered in the sheet weeks ahead, so the latest week with a
    pick is not "now". The current week is the latest week whose games have
    actually kicked off."""

    def test_uses_the_latest_started_game_week(self):
        assert resolve_current_week(pick_weeks=range(1, 15), started_game_weeks=[1, 2, 3]) == 3

    def test_ignores_picks_entered_for_future_weeks(self):
        """The 2025 sheet held all 14 weeks from day one."""
        assert resolve_current_week(pick_weeks=range(1, 15), started_game_weeks=[1]) == 1

    def test_clamps_to_the_last_week_with_picks(self):
        """Games exist through week 18; picks stop at 14."""
        assert resolve_current_week(pick_weeks=range(1, 15), started_game_weeks=range(1, 19)) == 14

    def test_before_kickoff_falls_back_to_the_first_week(self):
        assert resolve_current_week(pick_weeks=[1, 2, 3], started_game_weeks=[]) == 1

    def test_no_picks_at_all(self):
        assert resolve_current_week(pick_weeks=[], started_game_weeks=[]) == 1
