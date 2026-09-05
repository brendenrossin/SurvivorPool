"""Pure helpers behind the dashboard's cached data functions."""

from app.dashboard_data import count_completed_weeks, decide_week_results


class TestCountCompletedWeeks:
    """"Weeks Completed" counted weeks that had picks, so it read 1 before a
    single game of the season had been played. A round is over when its games
    are final, not when someone has filled in the sheet."""

    def test_a_week_is_complete_only_when_every_game_is_final(self):
        assert count_completed_weeks({1: ["final", "final"]}) == 1
        assert count_completed_weeks({1: ["final", "pre"]}) == 0

    def test_picks_entered_before_kickoff_do_not_complete_a_round(self):
        """The 2026 case: one week of picks, every game still 'pre'."""
        assert count_completed_weeks({1: ["pre"] * 16}) == 0

    def test_counts_only_the_finished_weeks(self):
        """2025: weeks 1-14 played, 15-16 on the schedule but unplayed."""
        statuses = {w: ["final"] * 16 for w in range(1, 15)}
        statuses.update({15: ["pre"] * 16, 16: ["pre"] * 16})
        assert count_completed_weeks(statuses) == 14

    def test_no_games_at_all(self):
        assert count_completed_weeks({}) == 0

    def test_a_week_with_no_games_is_not_complete(self):
        assert count_completed_weeks({1: []}) == 0


class TestDecideWeekResults:
    """The survivor tie rule, finally reachable by a test.

    This lived inline in render_weekly_picks_chart, so deleting it passed the
    entire suite. A tie eliminates BOTH teams' pickers.
    """

    def test_decided_game_splits_winner_and_loser(self):
        # 2025 week 14: NO 24, TB 20 - the game that ended the pool
        assert decide_week_results([("final", "TB", "NO", 20, 24)]) == {
            "TB": "lost", "NO": "won",
        }

    def test_home_win(self):
        assert decide_week_results([("final", "DET", "DAL", 44, 30)]) == {
            "DET": "won", "DAL": "lost",
        }

    def test_a_tie_eliminates_both_teams(self):
        """The rule the whole function exists for."""
        assert decide_week_results([("final", "NYG", "WAS", 17, 17)]) == {
            "NYG": "lost", "WAS": "lost",
        }

    def test_unplayed_games_are_pending(self):
        assert decide_week_results([("pre", "SEA", "NE", None, None)]) == {
            "SEA": "pending", "NE": "pending",
        }
        assert decide_week_results([("scheduled", "SEA", "NE", None, None)]) == {
            "SEA": "pending", "NE": "pending",
        }

    def test_a_live_game_is_pending_not_decided(self):
        """A team leading at half has not survived anything yet."""
        assert decide_week_results([("in", "KC", "HOU", 10, 20)]) == {
            "KC": "pending", "HOU": "pending",
        }

    def test_final_without_scores_is_not_decided(self):
        """Ingestion can mark a game final before the scores land."""
        assert decide_week_results([("final", "KC", "HOU", None, None)]) == {
            "KC": "pending", "HOU": "pending",
        }

    def test_no_games(self):
        assert decide_week_results([]) == {}

    def test_every_team_in_a_full_week_gets_a_verdict(self):
        """2025 week 14: 14 games, 28 teams, all final."""
        games = [("final", f"H{i}", f"A{i}", 20 + i, 10) for i in range(14)]
        assert len(decide_week_results(games)) == 28

    def test_a_decided_verdict_is_never_overwritten_by_a_pending_one(self):
        """Duplicate rows for one team - a rescheduled game left in the table -
        must not downgrade a settled result to pending, in either order."""
        decided = ("final", "TB", "NO", 20, 24)
        pending = ("pre", "TB", "NO", None, None)
        assert decide_week_results([decided, pending])["TB"] == "lost"
        assert decide_week_results([pending, decided])["TB"] == "lost"
