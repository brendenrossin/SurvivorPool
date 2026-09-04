"""Pure helpers behind the dashboard's cached data functions."""

from app.dashboard_data import count_completed_weeks


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
