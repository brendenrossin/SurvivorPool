"""The scoreboard's week, and the card view models.

The scoreboard's notion of "current" is deliberately NOT the grid's. The grid
leads with the last week that kicked off, because that is the last week whose
picks may be published. The scoreboard rolls forward once the current week is
finished, so a Tuesday shows what is coming rather than what is settled.
"""

from app.live_scores import build_scoreboard, resolve_scoreboard_week


class TestResolveScoreboardWeek:
    """Driven by whether the games finished, not by the day of the week - the
    old rule added one every Tuesday after 04:00 UTC regardless of play."""

    def test_an_unfinished_week_does_not_roll(self):
        """Sunday afternoon: the week is live, stay on it."""
        assert resolve_scoreboard_week(5, {5: ["final", "in", "pre"]}) == 5

    def test_a_finished_week_rolls_forward(self):
        """Tuesday: Monday night is over, show week 6."""
        assert resolve_scoreboard_week(5, {5: ["final"] * 14, 6: ["pre"] * 16}) == 6

    def test_it_does_not_roll_past_the_schedule(self):
        """2025's games table ends at week 16; never point past it."""
        assert resolve_scoreboard_week(16, {16: ["final"] * 16}) == 16

    def test_a_week_with_no_games_does_not_roll(self):
        assert resolve_scoreboard_week(5, {5: []}) == 5

    def test_it_rolls_only_one_week(self):
        """Several finished weeks in the table must not skip the season."""
        statuses = {w: ["final"] * 16 for w in range(1, 15)}
        statuses[15] = ["pre"] * 16
        assert resolve_scoreboard_week(14, statuses) == 15

    def test_no_games_at_all(self):
        assert resolve_scoreboard_week(1, {}) == 1


WK14 = [
    dict(game_id="g1", status="final", home_team="TB", away_team="NO",
         home_score=20, away_score=24, winner_abbr="NO",
         kickoff=None, favorite_team=None, point_spread=None),
    dict(game_id="g2", status="final", home_team="ATL", away_team="SEA",
         home_score=9, away_score=37, winner_abbr="SEA",
         kickoff=None, favorite_team=None, point_spread=None),
    dict(game_id="g3", status="pre", home_team="KC", away_team="DEN",
         home_score=None, away_score=None, winner_abbr=None,
         kickoff=None, favorite_team="Kansas City Chiefs", point_spread=3.0),
]
COUNTS = {"TB": 16, "SEA": 1}


class TestBuildScoreboard:
    """2025 week 14 - 16 entrants on Tampa Bay, one on Seattle."""

    def test_only_games_with_a_picked_team_are_shown(self):
        cards = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)
        assert [c["game_id"] for c in cards] == ["g1", "g2"]

    def test_pick_counts_land_on_the_right_side(self):
        card = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]
        assert card["home"]["team"] == "TB" and card["home"]["picks"] == 16
        assert card["away"]["team"] == "NO" and card["away"]["picks"] == 0

    def test_a_final_game_carries_the_outcome(self):
        card = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]
        assert card["home"]["outcome"] == "lost"
        assert card["away"]["outcome"] == "won"

    def test_an_unplayed_week_reveals_no_pick_data_at_all(self):
        """THE LEAK TEST. A week that has not kicked off shows the full slate
        with no counts and no filtering - filtering the slate to picked teams
        is itself a disclosure of the field's picks, by omission rather than by
        a number, days before kickoff."""
        cards = build_scoreboard(WK14, COUNTS, {}, reveal_picks=False)
        assert len(cards) == 3, "an unplayed week shows every game"
        assert all(c["away"]["picks"] == 0 and c["home"]["picks"] == 0 for c in cards)
        assert not any(c["has_picks"] for c in cards)

    def test_an_unplayed_week_leaks_nothing_through_the_outcome_split_either(self):
        results = {"g1": {"survived": 0, "eliminated": 16}}
        cards = build_scoreboard(WK14, COUNTS, results, reveal_picks=False)
        assert all(c["eliminated"] == 0 and c["survived"] == 0 for c in cards)

    def test_live_games_sort_before_everything(self):
        games = [dict(WK14[0]), dict(WK14[1])]
        games[1]["status"] = "in"
        cards = build_scoreboard(games, COUNTS, {}, reveal_picks=True)
        assert cards[0]["game_id"] == "g2"

    def test_the_line_is_shown_when_the_database_has_one(self):
        cards = build_scoreboard(WK14, {"KC": 1}, {}, reveal_picks=True)
        assert cards[0]["line"] == "KC -3.0"

    def test_no_line_when_the_database_has_none(self):
        """2025 carries spreads on only 31 of its 240 games."""
        assert build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]["line"] is None

    def test_the_elimination_split_rides_on_the_card(self):
        results = {"g1": {"survived": 0, "eliminated": 16}}
        card = build_scoreboard(WK14, COUNTS, results, reveal_picks=True)[0]
        assert card["eliminated"] == 16 and card["survived"] == 0

    def test_no_picks_at_all_shows_the_full_slate(self):
        """Pre-season: the dashboard should still be worth opening."""
        cards = build_scoreboard(WK14, {}, {}, reveal_picks=True)
        assert len(cards) == 3
