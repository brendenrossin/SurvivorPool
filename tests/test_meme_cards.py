"""Notable picks, as ranked cards."""

from types import SimpleNamespace

from api.odds_providers import ODDS_API_TEAM_NAMES
from app.meme_cards import big_balls_card_rows, dumbest_card_rows
from app.odds_helpers import get_team_name_to_abbr_mapping
from app.pick_scoring import (dumbness_score, rank_dumbest_picks,
                              shape_dumbest_pick, unmapped_favourite_names,
                              upset_shock)

DUMBEST = [
    {"week": 3, "team": "ATL", "opponent": "CAR", "margin": 30, "eliminated_count": 12,
     "point_spread": None, "was_favorite": False},
    {"week": 1, "team": "MIA", "opponent": "IND", "margin": 25, "eliminated_count": 2,
     "point_spread": None, "was_favorite": False},
]

# 2026 week 1, verbatim from production. The case the ranking is calibrated
# against: ranking on raw margin puts DEN - a 3-point *underdog* - first, and
# LAC, a 10-point favourite that ended 118 of 300 entrants, third.
WEEK_ONE = [
    {"week": 1, "team": "LAC", "opponent": "ARI", "margin": 12,
     "eliminated_count": 118, "point_spread": 10.0, "was_favorite": True},
    {"week": 1, "team": "DEN", "opponent": "KC", "margin": 21,
     "eliminated_count": 1, "point_spread": 3.0, "was_favorite": False},
    {"week": 1, "team": "LAR", "opponent": "SF", "margin": 20,
     "eliminated_count": 1, "point_spread": 3.5, "was_favorite": True},
    {"week": 1, "team": "DAL", "opponent": "NYG", "margin": 8,
     "eliminated_count": 1, "point_spread": 3.0, "was_favorite": True},
]
# Shaped like every 2025 row: point_spread is NULL all season, so was_underdog
# never fires and the panel is road wins with counts of 1.
BIG_BALLS = [
    {"week": 14, "team": "SEA", "opponent": "ATL", "road_win": True,
     "was_underdog": False, "point_spread": None, "favorite_team": None,
     "big_balls_count": 1},
]


class TestUpsetShock:
    """How much worse the result was than the market expected."""

    def test_a_favourite_losing_is_worse_than_the_scoreline(self):
        """LAC: 10-point favourite, lost by 12 - a 22-point swing."""
        assert upset_shock(12, 10.0, was_favorite=True) == 22.0

    def test_an_underdog_losing_is_better_than_the_scoreline(self):
        """DEN: 3-point underdog, lost by 21. Three of those were priced in."""
        assert upset_shock(21, 3.0, was_favorite=False) == 18.0

    def test_no_spread_falls_back_to_the_raw_margin(self):
        """2025 has odds for 31 of 240 games; without this the section empties."""
        assert upset_shock(30, None, was_favorite=False) == 30

    def test_an_underdog_losing_narrowly_scores_below_the_margin(self):
        assert upset_shock(3, 10.0, was_favorite=False) == -7.0


class TestDumbnessScore:
    def test_multiplies_shock_by_the_field_it_took(self):
        assert dumbness_score(12, 10.0, True, 118) == 22.0 * 118

    def test_a_popular_pick_survives_a_negative_shock(self):
        """Losing by less than the spread is still losing. Without the floor a
        118-entrant wipeout would score negative and sort below a 1-entrant one."""
        assert dumbness_score(3, 10.0, False, 118) == 118

    def test_nobody_eliminated_scores_nothing(self):
        assert dumbness_score(40, 14.0, True, 0) == 0


class TestRankDumbestPicks:
    def test_the_heavy_favourite_that_took_the_pool_leads(self):
        assert [p["team"] for p in rank_dumbest_picks(WEEK_ONE)][0] == "LAC"

    def test_an_underdog_blowout_does_not_lead(self):
        """The bug this replaces: ORDER BY margin DESC put DEN first."""
        assert rank_dumbest_picks(WEEK_ONE)[0]["team"] != "DEN"

    def test_full_order_on_the_real_week(self):
        assert [p["team"] for p in rank_dumbest_picks(WEEK_ONE)] == [
            "LAC", "LAR", "DEN", "DAL"]

    def test_caps_at_five(self):
        assert len(rank_dumbest_picks(WEEK_ONE * 4)) == 5

    def test_respects_an_explicit_limit(self):
        assert len(rank_dumbest_picks(WEEK_ONE, limit=2)) == 2

    def test_empty_gives_empty(self):
        assert rank_dumbest_picks([]) == []

    def test_a_full_tie_is_ordered_deterministically(self):
        """2025 has no spread for 209 of 240 games and most weeks eliminate one
        entrant, so rows tie on score, count and margin alike. Without a total
        key the visible top five reshuffles on every cache refresh."""
        a = {"week": 5, "team": "AAA", "opponent": "X", "margin": 10,
             "eliminated_count": 1, "point_spread": None, "was_favorite": False}
        b = {**a, "team": "BBB"}
        assert rank_dumbest_picks([a, b]) == rank_dumbest_picks([b, a])

    def test_ties_break_on_the_field_eliminated(self):
        """Equal scores must not be left to database row order."""
        a = {"week": 1, "team": "AAA", "opponent": "X", "margin": 10,
             "eliminated_count": 2, "point_spread": None, "was_favorite": False}
        b = {**a, "team": "BBB", "margin": 20, "eliminated_count": 1}
        assert [p["team"] for p in rank_dumbest_picks([b, a])] == ["AAA", "BBB"]


class TestDumbestCardRows:
    def test_ranks_from_one(self):
        assert [r["rank"] for r in dumbest_card_rows(DUMBEST)] == [1, 2]

    def test_headline_is_the_margin(self):
        assert dumbest_card_rows(DUMBEST)[0]["headline"] == "30"

    def test_matchup_reads_as_a_matchup(self):
        assert dumbest_card_rows(DUMBEST)[0]["matchup"] == "ATL vs CAR"

    def test_victim_line_is_singular_for_one(self):
        rows = dumbest_card_rows([{**DUMBEST[0], "eliminated_count": 1}])
        assert rows[0]["detail"] == "1 player eliminated"

    def test_victim_line_is_plural_for_many(self):
        assert dumbest_card_rows(DUMBEST)[0]["detail"] == "12 players eliminated"

    def test_caps_at_five(self):
        assert len(dumbest_card_rows(DUMBEST * 9)) == 5

    def test_carries_no_emoji(self):
        joined = "".join(str(v) for v in dumbest_card_rows(DUMBEST)[0].values())
        assert all(ord(ch) < 0x2500 for ch in joined)

    def test_empty_gives_empty(self):
        assert dumbest_card_rows([]) == []

    def test_a_favourite_is_badged_with_its_spread(self):
        assert dumbest_card_rows(WEEK_ONE)[0]["badges"] == ["10-PT FAVORITE"]

    def test_a_whole_number_spread_loses_its_decimal(self):
        """7.0 from the database must not reach a card as "7.0-PT"."""
        rows = dumbest_card_rows([{**WEEK_ONE[0], "point_spread": 7.0}])
        assert rows[0]["badges"] == ["7-PT FAVORITE"]

    def test_a_spread_that_is_not_a_number_is_dropped_not_rendered(self):
        """It is a Float column fed by an external odds feed and printed on a
        public page. A string used to raise; nan printed as "nan-PT FAVORITE"."""
        for junk in ("ten", float("nan"), float("inf"), -3.0, 0):
            rows = dumbest_card_rows([{**WEEK_ONE[0], "point_spread": junk}])
            assert rows[0]["badges"] == [], junk

    def test_a_numeric_string_spread_still_renders(self):
        rows = dumbest_card_rows([{**WEEK_ONE[0], "point_spread": "10.0"}])
        assert rows[0]["badges"] == ["10-PT FAVORITE"]

    def test_a_half_point_spread_keeps_it(self):
        rows = dumbest_card_rows([WEEK_ONE[2]])
        assert rows[0]["badges"] == ["3.5-PT FAVORITE"]

    def test_an_underdog_is_not_badged(self):
        """The badge explains why a small loss outranks a big one. On an
        underdog it would say the opposite of what the ranking did."""
        assert dumbest_card_rows([WEEK_ONE[1]])[0]["badges"] == []

    def test_no_spread_means_no_badge(self):
        assert dumbest_card_rows(DUMBEST)[0]["badges"] == []

    def test_the_score_is_never_shown(self):
        """The rank key orders the list; it must not reach the page. "2596"
        means nothing on a card, while the numbers it is built from mean
        everything."""
        pick = WEEK_ONE[0]
        score = dumbness_score(pick["margin"], pick["point_spread"],
                               pick["was_favorite"], pick["eliminated_count"])
        row = dumbest_card_rows(WEEK_ONE)[0]
        joined = "".join(str(v) for v in row.values())
        for rendering in (str(score), str(int(score))):
            assert rendering not in joined


def _row(**kw):
    """One dumbest_query result row."""
    base = dict(week=1, team_abbr="LAC", home_team="ARI", away_team="LAC",
                margin=12, eliminated_count=118, point_spread=10.0,
                favorite_team="Los Angeles Chargers")
    return SimpleNamespace(**{**base, **kw})


class TestShapeDumbestPick:
    """The bridge from `games.favorite_team` (a full team name) to
    `picks.team_abbr` (an abbreviation). Deleting it left the whole suite green
    while every favourite silently scored as an underdog - strictly worse than
    the raw-margin ranking it replaced."""

    MAP = {"Los Angeles Chargers": "LAC", "Kansas City Chiefs": "KC"}

    def test_a_full_team_name_resolves_to_the_picked_abbreviation(self):
        assert shape_dumbest_pick(_row(), self.MAP)["was_favorite"] is True

    def test_the_other_team_being_favourite_is_not_favourite(self):
        row = _row(team_abbr="ARI", favorite_team="Los Angeles Chargers")
        assert shape_dumbest_pick(row, self.MAP)["was_favorite"] is False

    def test_a_row_that_already_stores_an_abbreviation_still_resolves(self):
        """Older odds rows wrote the abbreviation directly."""
        assert shape_dumbest_pick(_row(favorite_team="LAC"), self.MAP)["was_favorite"] is True

    def test_no_favourite_recorded_is_not_a_favourite(self):
        shaped = shape_dumbest_pick(_row(favorite_team=None), self.MAP)
        assert shaped["was_favorite"] is False
        assert shaped["favourite_known"] is False

    def test_opponent_is_the_other_side_of_the_game(self):
        assert shape_dumbest_pick(_row(), self.MAP)["opponent"] == "ARI"

    def test_an_unmapped_name_is_reported(self):
        rows = [_row(favorite_team="Las Vegas Raiders of San Antonio")]
        assert unmapped_favourite_names(rows, self.MAP) == [
            "Las Vegas Raiders of San Antonio"]

    def test_a_known_name_is_not_reported(self):
        assert unmapped_favourite_names([_row()], self.MAP) == []

    def test_an_abbreviation_is_not_reported_as_unmapped(self):
        assert unmapped_favourite_names([_row(favorite_team="LAC")], self.MAP) == []


class TestOddsNamesResolve:
    def test_every_name_the_odds_feed_can_write_resolves_to_its_abbreviation(self):
        """`favorite_team` is written verbatim from The Odds API. If a franchise
        renames upstream and the seed map is not updated, that team silently
        ranks as an underdog forever. Fail the build instead."""
        seed = get_team_name_to_abbr_mapping()
        assert {n: seed.get(n) for n in ODDS_API_TEAM_NAMES} == ODDS_API_TEAM_NAMES


class TestBigBallsCardRows:
    def test_road_win_uses_at_not_vs(self):
        assert big_balls_card_rows(BIG_BALLS)[0]["matchup"] == "SEA at ATL"

    def test_home_win_uses_vs(self):
        rows = big_balls_card_rows([{**BIG_BALLS[0], "road_win": False}])
        assert rows[0]["matchup"] == "SEA vs ATL"

    def test_road_badge_present(self):
        assert "ROAD" in big_balls_card_rows(BIG_BALLS)[0]["badges"]

    def test_no_underdog_badge_without_spread_data(self):
        # The whole 2025 season looks like this
        assert "UNDERDOG" not in big_balls_card_rows(BIG_BALLS)[0]["badges"]

    def test_underdog_badge_when_the_flag_is_set(self):
        rows = big_balls_card_rows([{**BIG_BALLS[0], "was_underdog": True}])
        assert "UNDERDOG" in rows[0]["badges"]

    def test_headline_is_the_player_count(self):
        assert big_balls_card_rows(BIG_BALLS)[0]["headline"] == "1"

    def test_headline_unit_agrees_with_the_count(self):
        assert big_balls_card_rows(BIG_BALLS)[0]["headline_unit"].startswith("player ")
        many = big_balls_card_rows([{**BIG_BALLS[0], "big_balls_count": 4}])
        assert many[0]["headline_unit"].startswith("players ")

    def test_carries_no_emoji(self):
        joined = "".join(str(v) for v in big_balls_card_rows(BIG_BALLS)[0].values())
        assert all(ord(ch) < 0x2500 for ch in joined)

    def test_empty_gives_empty(self):
        assert big_balls_card_rows([]) == []
