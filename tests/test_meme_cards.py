"""Notable picks, as ranked cards."""

from app.meme_cards import big_balls_card_rows, dumbest_card_rows

DUMBEST = [
    {"week": 3, "team": "ATL", "opponent": "CAR", "margin": 30, "eliminated_count": 12},
    {"week": 1, "team": "MIA", "opponent": "IND", "margin": 25, "eliminated_count": 2},
]
# Shaped like every 2025 row: point_spread is NULL all season, so was_underdog
# never fires and the panel is road wins with counts of 1.
BIG_BALLS = [
    {"week": 14, "team": "SEA", "opponent": "ATL", "road_win": True,
     "was_underdog": False, "point_spread": None, "favorite_team": None,
     "big_balls_count": 1},
]


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
