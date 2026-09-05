"""Pure helpers behind the dashboard's cached data functions."""

import pytest

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
class TestBuildAttritionRows:
    """The field's week-by-week decline. Pure, so the arithmetic is testable
    without a database."""

    ELIMS_2025 = {1: 6, 2: 8, 3: 67, 4: 44, 5: 53, 6: 13, 7: 1,
                  8: 21, 9: 7, 10: 11, 11: 0, 12: 0, 13: 2, 14: 18}

    def test_matches_the_real_2025_shape(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(252, self.ELIMS_2025, list(range(1, 15)))
        assert rows[0]["entering"] == 252
        assert rows[0]["remaining"] == 246
        assert rows[2]["entering"] == 238
        assert rows[5]["entering"] == 74
        assert rows[-1]["remaining"] == 1

    def test_entering_equals_previous_remaining(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(20, {1: 5, 2: 3, 3: 0}, [1, 2, 3])
        for prev, cur in zip(rows, rows[1:]):
            assert cur["entering"] == prev["remaining"]

    def test_a_week_with_no_eliminations_is_flat(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(10, {1: 0}, [1])
        assert rows[0]["entering"] == rows[0]["remaining"] == 10
        assert rows[0]["pct_out"] == 0.0

    def test_missing_week_key_counts_as_zero(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(10, {}, [1, 2])
        assert [r["remaining"] for r in rows] == [10, 10]

    def test_pct_out_is_of_players_entering_that_week(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(200, {1: 50}, [1])
        assert rows[0]["pct_out"] == pytest.approx(25.0)

    def test_no_entrants_does_not_divide_by_zero(self):
        from app.dashboard_data import build_attrition_rows
        assert build_attrition_rows(0, {}, [1])[0]["pct_out"] == 0.0

    def test_weeks_are_sorted_even_if_input_is_not(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(10, {1: 1, 2: 1}, [2, 1])
        assert [r["week"] for r in rows] == [1, 2]

    def test_empty_weeks_gives_empty_series(self):
        from app.dashboard_data import build_attrition_rows
        assert build_attrition_rows(252, {}, []) == []


class TestRankDoomTeams:
    def test_orders_by_eliminations_descending(self):
        from app.dashboard_data import rank_doom_teams
        out = rank_doom_teams([("LAC", 32, 5), ("GB", 73, 3), ("ATL", 28, 3)])
        assert [t["team"] for t in out] == ["GB", "LAC", "ATL"]

    def test_ties_break_alphabetically_for_a_stable_order(self):
        from app.dashboard_data import rank_doom_teams
        out = rank_doom_teams([("MIN", 3, 2), ("PIT", 3, 4), ("NE", 3, 1)])
        assert [t["team"] for t in out] == ["MIN", "NE", "PIT"]

    def test_clamps_a_negative_field_to_zero(self):
        from app.dashboard_data import build_attrition_rows
        rows = build_attrition_rows(5, {1: 9}, [1])
        assert rows[0]["remaining"] == 0
        assert rows[0]["pct_out"] == 100.0

    def test_drops_null_team_rows(self):
        # A missed pick has team_abbr NULL. It eliminates players but is not a
        # team, and 2025 has 233 such picks - they would top the ranking.
        from app.dashboard_data import rank_doom_teams
        out = rank_doom_teams([("GB", 73, 3), (None, 233, 5)])
        assert [t["team"] for t in out] == ["GB"]

    def test_empty_input_gives_empty_output(self):
        from app.dashboard_data import rank_doom_teams
        assert rank_doom_teams([]) == []


class TestClampPicksToWeek:
    """Rule: never surface a pick for a week that has not kicked off. The
    sheet holds future weeks from day one."""

    def test_drops_future_weeks(self):
        from app.dashboard_data import clamp_picks_to_week
        picks = [{"week": 1}, {"week": 2}, {"week": 3}]
        assert [p["week"] for p in clamp_picks_to_week(picks, 2)] == [1, 2]

    def test_keeps_everything_at_or_before_the_week(self):
        from app.dashboard_data import clamp_picks_to_week
        assert len(clamp_picks_to_week([{"week": 1}, {"week": 2}], 2)) == 2

    def test_clamp_to_none_is_a_no_op(self):
        from app.dashboard_data import clamp_picks_to_week
        picks = [{"week": 9}]
        assert clamp_picks_to_week(picks, None) == picks

    def test_empty_picks_stay_empty(self):
        from app.dashboard_data import clamp_picks_to_week
        assert clamp_picks_to_week([], 3) == []


class TestSelectAttritionWeeks:
    """Before any kickoff there is no attrition to report. Without this the
    tracker renders 2026's unplayed week 1 as "5 entered, 0 eliminated"."""

    def test_returns_empty_when_no_week_has_started(self):
        from app.dashboard_data import select_attrition_weeks
        assert select_attrition_weeks([1], None) == []

    def test_drops_weeks_past_kickoff(self):
        from app.dashboard_data import select_attrition_weeks
        assert select_attrition_weeks([1, 2, 3, 4], 2) == [1, 2]

    def test_keeps_the_started_week_itself(self):
        from app.dashboard_data import select_attrition_weeks
        assert select_attrition_weeks([1, 2], 2) == [1, 2]

    def test_sorts_its_input(self):
        from app.dashboard_data import select_attrition_weeks
        assert select_attrition_weeks([3, 1, 2], 3) == [1, 2, 3]
