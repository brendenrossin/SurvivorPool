"""The field's decline, as figures."""

import pytest

from app.attrition import (ANCHOR_LABEL, build_attrition_chart,
                           build_sparkline, describe_worst_stretch)

# The real 2025 opening, including the week 3-5 cliff that motivated this.
ROWS = [
    {"week": 1, "entering": 252, "eliminated": 6, "remaining": 246, "pct_out": 2.4},
    {"week": 2, "entering": 246, "eliminated": 8, "remaining": 238, "pct_out": 3.3},
    {"week": 3, "entering": 238, "eliminated": 67, "remaining": 171, "pct_out": 28.2},
    {"week": 4, "entering": 171, "eliminated": 44, "remaining": 127, "pct_out": 25.7},
    {"week": 5, "entering": 127, "eliminated": 53, "remaining": 74, "pct_out": 41.7},
]


# 2026 after one week. A single row is what broke both figures: `mode="lines"`
# draws a one-point line as nothing, so the KPI card held an empty box.
ONE_WEEK = [
    {"week": 1, "entering": 300, "eliminated": 121, "remaining": 179,
     "pct_out": 40.3},
]


class TestSparkline:
    def test_plots_the_anchor_then_one_point_per_week(self):
        assert len(build_sparkline(ROWS).data[0].x) == len(ROWS) + 1

    def test_opens_on_the_field_that_entered(self):
        assert build_sparkline(ROWS).data[0].y[0] == 252

    def test_plots_remaining_not_eliminated(self):
        assert list(build_sparkline(ROWS).data[0].y)[1:] == [246, 238, 171, 127, 74]

    def test_is_short_enough_to_sit_inside_a_kpi_card(self):
        assert build_sparkline(ROWS).layout.height <= 60

    def test_hides_both_axes(self):
        fig = build_sparkline(ROWS)
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_a_single_played_week_still_draws_a_line(self):
        """Two points, not one: a one-point line renders as nothing at all."""
        assert len(build_sparkline(ONE_WEEK).data[0].x) == 2

    def test_a_single_played_week_shows_the_drop(self):
        assert list(build_sparkline(ONE_WEEK).data[0].y) == [300, 179]

    def test_empty_rows_gives_an_empty_figure_not_a_crash(self):
        assert build_sparkline([]).data == ()


class TestAttritionChart:
    def test_plots_remaining_not_eliminated(self):
        assert list(build_attrition_chart(ROWS).data[0].y)[1:] == [246, 238, 171, 127, 74]

    def test_opens_on_the_field_that_entered(self):
        fig = build_attrition_chart(ONE_WEEK)
        assert list(fig.data[0].x) == [0, 1]
        assert list(fig.data[0].y) == [300, 179]

    def test_labels_the_anchor_rather_than_naming_a_week_zero(self):
        axis = build_attrition_chart(ROWS).layout.xaxis
        assert axis.ticktext == (ANCHOR_LABEL, "W1", "W2", "W3", "W4", "W5")
        assert axis.tickvals == (0, 1, 2, 3, 4, 5)

    def test_anchor_hover_names_the_field_that_entered(self):
        assert "252 entered" in build_attrition_chart(ROWS).data[0].hovertext[0]

    def test_marks_the_current_week(self):
        assert len(build_attrition_chart(ROWS, current_week=3).layout.shapes) >= 1

    def test_no_marker_when_current_week_is_none(self):
        assert build_attrition_chart(ROWS).layout.shapes == ()

    def test_no_marker_for_a_week_not_in_the_series(self):
        assert build_attrition_chart(ROWS, current_week=99).layout.shapes == ()

    def test_hover_carries_the_elimination_count(self):
        """Offset by one: index 0 is the anchor, so week 3 is index 3."""
        hover = build_attrition_chart(ROWS).data[0].hovertext[3]
        assert "Week 3" in hover and "67 out (28.2%)" in hover

    def test_empty_rows_gives_an_empty_figure(self):
        assert build_attrition_chart([]).data == ()


class TestDescribeWorstStretch:
    def test_names_the_cliff(self):
        # Weeks 3-5 remove 164 - the story the donut could not tell
        out = describe_worst_stretch(ROWS)
        assert "3" in out and "5" in out and "164" in out

    def test_returns_none_when_nobody_has_been_eliminated(self):
        flat = [{"week": 1, "entering": 5, "eliminated": 0,
                 "remaining": 5, "pct_out": 0.0}]
        assert describe_worst_stretch(flat) is None

    def test_returns_none_for_empty_rows(self):
        assert describe_worst_stretch([]) is None

    def test_handles_a_series_shorter_than_the_span(self):
        short = ROWS[:2]
        assert describe_worst_stretch(short) is not None
