"""The scoreboard's week, and the card view models.

The scoreboard's notion of "current" is deliberately NOT the grid's. The grid
leads with the last week that kicked off, because that is the last week whose
picks may be published. The scoreboard rolls forward once the current week is
finished, so a Tuesday shows what is coming rather than what is settled.
"""

from datetime import datetime, timezone

from app.live_scores import (
    build_scoreboard,
    resolve_scoreboard_week,
    should_reveal_picks,
)


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


class TestShouldRevealPicks:
    """The wiring-level leak, which the build_scoreboard tests could not catch.

    reveal_picks was first derived as `scoreboard_week <= played_week`. That
    ordering holds in exactly the case it most needed to exclude: before any
    game of the season starts, resolve_current_week falls back to the first
    week holding picks rather than reporting "nothing has started", so both
    weeks are 1 and 1 <= 1 is True. On live 2026 data that published all five
    entrants' week 1 picks nine days before kickoff, and filtered the slate
    from 16 games to 3 - disclosure by omission even without the counts.
    """

    def test_the_pre_season_case_that_shipped_broken(self):
        """2026 as it stands today: picks in for week 1, nothing kicked off."""
        assert should_reveal_picks(1, []) is False

    def test_a_week_that_has_kicked_off_reveals(self):
        assert should_reveal_picks(5, [1, 2, 3, 4, 5]) is True

    def test_a_rolled_forward_week_does_not_reveal(self):
        """Tuesday of week 6: weeks 1-5 played, the scoreboard shows week 6."""
        assert should_reveal_picks(6, [1, 2, 3, 4, 5]) is False

    def test_a_pool_starting_after_week_one_does_not_reveal(self):
        """The other resolve_current_week fallback: picks start at week 5 while
        the NFL has already played 1-4, so played_week is 5 and the old
        comparison passed despite week 5 not having started."""
        assert should_reveal_picks(5, [1, 2, 3, 4]) is False

    def test_no_games_started_at_all(self):
        assert should_reveal_picks(1, []) is False


class TestSortingAndTimestamps:
    """Behaviours no test pinned, found by mutation testing."""

    def test_every_rendered_card_agrees_about_whether_picks_are_shown(self):
        """Why the sort has no has_picks tiebreak: the flag is uniform across
        the cards in every reachable state, so it could never discriminate.
        Asserted rather than reasoned about, since the filter and the flag are
        set in different places."""
        for reveal, counts in ((True, {"TB": 16}), (True, {}), (False, {"TB": 16})):
            cards = build_scoreboard(WK14, counts, {}, reveal_picks=reveal)
            assert len({c["has_picks"] for c in cards}) <= 1

    def test_an_unfinished_game_carries_no_outcome_even_with_a_winner_set(self):
        """The `status == "final"` guard. Ingestion setting winner_abbr early
        must not mark anyone as having survived."""
        games = [dict(game_id="g", status="in", home_team="TB", away_team="NO",
                      home_score=20, away_score=24, winner_abbr="NO",
                      kickoff=None, favorite_team=None, point_spread=None)]
        card = build_scoreboard(games, {"TB": 16}, {}, reveal_picks=True)[0]
        assert card["home"]["outcome"] is None and card["away"]["outcome"] is None

    def test_naive_and_aware_kickoffs_sort_together(self):
        """Postgres returns aware datetimes, SQLite naive ones. Mixing them in
        a sort key raises TypeError."""
        base = dict(status="pre", home_score=None, away_score=None,
                    winner_abbr=None, favorite_team=None, point_spread=None)
        games = [
            dict(base, game_id="aware", home_team="KC", away_team="DEN",
                 kickoff=datetime(2025, 9, 14, 20, 25, tzinfo=timezone.utc)),
            dict(base, game_id="naive", home_team="TB", away_team="NO",
                 kickoff=datetime(2025, 9, 14, 17, 0)),
            dict(base, game_id="none", home_team="SEA", away_team="ATL",
                 kickoff=None),
        ]
        cards = build_scoreboard(games, {}, {}, reveal_picks=True)
        assert [c["game_id"] for c in cards] == ["none", "naive", "aware"]

    def test_games_sharing_a_kickoff_keep_a_stable_order(self):
        """Most of a Sunday slate kicks off at the same minute. Without a total
        ordering those ties fall back to database row order and the cards
        shuffle between reruns."""
        at = datetime(2025, 12, 7, 18, 0, tzinfo=timezone.utc)
        base = dict(status="final", home_score=20, away_score=10,
                    winner_abbr=None, favorite_team=None, point_spread=None,
                    kickoff=at)
        games = [
            dict(base, game_id="c", home_team="TB", away_team="NO"),
            dict(base, game_id="a", home_team="KC", away_team="DEN"),
            dict(base, game_id="b", home_team="SEA", away_team="ATL"),
        ]
        order = [c["game_id"] for c in build_scoreboard(games, {}, {}, True)]
        assert order == ["a", "b", "c"]
        assert order == [c["game_id"] for c in
                         build_scoreboard(list(reversed(games)), {}, {}, True)]
