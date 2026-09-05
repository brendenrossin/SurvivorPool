"""Row selection and cell styling for the weekly picks grid.

The grid leads with the current week: rows are the teams picked that week,
ordered by that week's count, padded out with the season's most-picked teams.
"""

import pytest

from app.picks_grid import (
    DANGER,
    _channels,
    _to_hsl,
    aggregate_picks,
    build_picks_grid,
    cell_edge,
    contrast_fill,
    contrast_ratio,
    eliminated_edge,
    eliminated_fill,
    ensure_contrast,
    history_ink,
    label_ink,
    mute_color,
    relative_luminance,
    resolve_current_week,
    select_grid_rows,
)

LIGHT_SURFACE = "#F8FAFC"
DARK_SURFACE = "#0B1220"
# Spans the real range in db/seed_team_map.json: LV black to PIT gold.
TEAM_COLORS = ["#D50A0A", "#311D00", "#002244", "#FB4F14", "#000000", "#FFB612",
               "#203731", "#00338D", "#0B162A", "#003594", "#D3BC8D", "#69BE28"]

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
    # DEN/CIN orange, luminance .26. This case asserted False, because it was
    # written against the 0.45 threshold rather than against contrast: white
    # ink gives 3.37:1 here and dark ink gives 5.84:1, so white was the wrong
    # answer and the test was encoding the bug. The crossover is 0.1791.
    ("#FB4F14", True),
])
def test_label_ink_contrasts_with_the_fill(hex_color, expected_dark):
    """Ink is computed from contrast, never assumed."""
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


class TestFigureLayout:
    """The grid computes its own height and label room. Both were shipped wrong
    once - the height by routing through CHART_CONFIGS, the labels by trusting
    an 8px margin - so they get asserted rather than eyeballed."""

    def _figure(self, rows, weeks):
        counts = {(w, t): 1 for w in weeks for t in rows}
        return build_picks_grid(
            weeks=weeks, rows=rows, counts=counts,
            week_totals={w: len(rows) for w in weeks},
            team_colors={t: "#004C54" for t in rows},
            current_week=weeks[-1],
        )

    def test_height_scales_with_row_count(self):
        assert self._figure(["PHI", "ARI"], [1]).layout.height == 2 * 34 + 120
        assert self._figure(["PHI"] * 10, [1]).layout.height == 10 * 34 + 120

    def test_axes_claim_room_for_their_labels(self):
        """Team abbreviations and week headers are clipped to a single
        character without this - the margins are only an 8px floor."""
        fig = self._figure(["PHI", "ARI"], [1, 2])
        assert fig.layout.yaxis.automargin is True
        assert fig.layout.xaxis.automargin is True

    def test_current_week_header_is_emphasised(self):
        fig = self._figure(["PHI"], [1, 2, 3])
        assert list(fig.layout.xaxis.ticktext) == ["W1", "W2", "<b>W3</b>"]


class TestAggregatePicks:
    """The clamp that stops unplayed weeks reaching the grid. Nothing tested it
    while it lived in main.py - deleting it passed the whole suite."""

    WEEKS = [
        {"week": 1, "teams": [{"team": "DEN", "count": 93}, {"team": "ARI", "count": 53}]},
        {"week": 2, "teams": [{"team": "DEN", "count": 40}]},
        {"week": 3, "teams": [{"team": "KC", "count": 12}]},
    ]

    def test_drops_weeks_that_have_not_kicked_off(self):
        counts, week_totals, _ = aggregate_picks(self.WEEKS, current_week=2)
        assert set(counts) == {(1, "DEN"), (1, "ARI"), (2, "DEN")}
        assert week_totals == {1: 146, 2: 40}

    def test_a_future_only_team_cannot_reach_the_grid_as_a_padded_row(self):
        """KC is picked in week 3 only. With current_week=2 it must not appear
        in season_totals, or select_grid_rows would pad it in as a blank row -
        revealing that someone has taken KC next week."""
        _, _, season_totals = aggregate_picks(self.WEEKS, current_week=2)
        assert "KC" not in season_totals
        assert season_totals == {"DEN": 133, "ARI": 53}
        assert "KC" not in select_grid_rows({"DEN": 40}, season_totals)

    def test_totals_span_every_visible_week(self):
        _, _, season_totals = aggregate_picks(self.WEEKS, current_week=3)
        assert season_totals == {"DEN": 133, "ARI": 53, "KC": 12}

    def test_no_visible_weeks(self):
        assert aggregate_picks(self.WEEKS, current_week=0) == ({}, {}, {})


class TestCellStyling:
    """Colour carries identity and emphasis here, so the current week's fill and
    the muted history are a contract, not a detail."""

    def _fills(self, as_percent=False):
        fig = build_picks_grid(
            weeks=[1, 2], rows=["DEN"],
            counts={(1, "DEN"): 1, (2, "DEN"): 200},
            week_totals={1: 252, 2: 400},
            team_colors={"DEN": "#FB4F14"}, current_week=2,
            as_percent=as_percent, background="#ffffff",
        )
        return fig

    def test_current_week_keeps_the_true_team_colour(self):
        shapes = self._fills().layout.shapes
        assert shapes[1].fillcolor == "#FB4F14"

    def test_earlier_weeks_are_muted_toward_the_surface(self):
        shapes = self._fills().layout.shapes
        assert shapes[0].fillcolor == mute_color("#FB4F14", "#ffffff")
        assert shapes[0].fillcolor != "#FB4F14"

    def test_a_single_picker_is_not_labelled_zero_percent(self):
        """1 of 252 is 0.4%, which "{:.0f}%" renders as "0%" in a cell that
        exists because it is not zero."""
        labels = [a.text for a in self._fills(as_percent=True).layout.annotations]
        assert labels == ["<1%", "50%"]

    def test_counts_are_the_default_label(self):
        labels = [a.text for a in self._fills().layout.annotations]
        assert labels == ["1", "200"]

    def test_empty_cells_are_not_drawn(self):
        fig = build_picks_grid(
            weeks=[1, 2], rows=["DEN", "KC"], counts={(1, "DEN"): 5},
            week_totals={1: 5}, team_colors={"DEN": "#FB4F14", "KC": "#E31837"},
            current_week=2,
        )
        assert len(fig.layout.shapes) == len(fig.layout.annotations) == 1


class TestResolveCurrentWeekWithGaps:
    """A gap in the pick weeks used to resolve to a week that had no picks at
    all - the grid would bold a column it never drew."""

    def test_falls_back_to_the_latest_week_that_actually_has_picks(self):
        assert resolve_current_week(pick_weeks=[1, 3], started_game_weeks=[1, 2]) == 1

    def test_the_resolved_week_always_has_picks(self):
        for started in ([1], [1, 2], [1, 2, 3], range(1, 19)):
            week = resolve_current_week(pick_weeks=[1, 3, 5], started_game_weeks=started)
            assert week in (1, 3, 5)


class TestEliminatedCell:
    """The busted current-week fill must never be readable as history.

    The grid already mutes toward the surface to mean "an earlier week". If
    elimination muted the same way the grid would lose its primary encoding, so
    elimination drains SATURATION while history drains LIGHTNESS.
    """

    def test_the_fill_is_achromatic(self):
        """Hue is the channel elimination gives up."""
        for team in TEAM_COLORS:
            fill = eliminated_fill(team, LIGHT_SURFACE)
            r, g, b = int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16)
            assert r == g == b, f"{team} -> {fill} kept a hue"

    def test_it_holds_the_lightness_its_history_cells_take(self):
        """Holding lightness constant is what proves the axes are different."""
        for team in TEAM_COLORS:
            history = mute_color(team, LIGHT_SURFACE)
            fill = eliminated_fill(team, LIGHT_SURFACE)
            assert abs(relative_luminance(fill) - relative_luminance(history)) < 0.02

    def test_it_never_equals_the_muted_history_colour(self):
        """The collision this whole design exists to prevent."""
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                assert eliminated_fill(team, surface) != mute_color(team, surface)

    def test_it_never_equals_the_current_week_colour(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                assert eliminated_fill(team, surface).lower() != team.lower()

    def test_it_follows_the_surface(self):
        """A light/dark reversal must be an argument change, not a rewrite."""
        for team in TEAM_COLORS:
            assert eliminated_fill(team, LIGHT_SURFACE) != eliminated_fill(team, DARK_SURFACE)

    def test_a_black_team_still_moves(self):
        """LV is already black; its history cell and its busted cell still differ."""
        assert eliminated_fill("#000000", LIGHT_SURFACE) != mute_color("#000000", LIGHT_SURFACE)


class TestEliminatedEdge:
    """The red border is the primary signal, so its contrast is computed."""

    def test_the_edge_clears_three_to_one_on_every_team_and_surface(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                fill = eliminated_fill(team, surface)
                assert contrast_ratio(eliminated_edge(fill, DANGER), fill) >= 3.0

    def test_the_token_passes_through_untouched_when_it_already_clears(self):
        """ensure_contrast is a no-op when the token already works."""
        assert ensure_contrast("#B91C1C", "#FFFFFF") == "#B91C1C"

    def test_contrast_ratio_is_symmetric_and_bounded(self):
        assert contrast_ratio("#000000", "#FFFFFF") == contrast_ratio("#FFFFFF", "#000000")
        assert round(contrast_ratio("#000000", "#FFFFFF"), 1) == 21.0
        assert contrast_ratio("#777777", "#777777") == 1.0


class TestLabelInkPicksTheBetterInk:
    """label_ink thresholded luminance at 0.45. The real crossover is 0.1791,
    so every fill between them got white ink where black reads better - five
    teams under the 4.5:1 small-text floor on the shipping light build."""

    def test_the_failing_teams_now_clear_the_small_text_floor(self):
        # CIN/DEN, MIA, CAR, LAC
        for team in ("#FB4F14", "#008E97", "#0085CA", "#0080C6"):
            assert contrast_ratio(label_ink(team), team) >= 4.5

    def test_it_always_picks_the_higher_contrast_ink(self):
        for team in TEAM_COLORS + ["#FB4F14", "#008E97", "#0085CA", "#0080C6"]:
            chosen = contrast_ratio(label_ink(team), team)
            best = max(contrast_ratio(ink, team) for ink in ("#0b0b0b", "#ffffff"))
            assert chosen == best, f"{team} took the worse ink"

    def test_the_extremes_are_unchanged(self):
        """LV black and PIT gold were already right; don't regress them."""
        assert label_ink("#000000") == "#ffffff"
        assert label_ink("#FFB612") == "#0b0b0b"


class TestSurfaceDerivedInk:
    """Three colours were hardcoded for a light surface. They invert on a dark
    one - a dark fill is the one that dissolves there, not a light one."""

    def test_a_cell_that_would_dissolve_gets_a_hairline(self):
        """A near-white fill on a near-white surface needs an edge."""
        assert cell_edge("#FEFEFE", LIGHT_SURFACE) != "#FEFEFE"

    def test_the_same_rule_catches_a_dark_fill_on_a_dark_surface(self):
        """The case the old > 0.6 threshold could not see."""
        assert cell_edge("#0B162A", DARK_SURFACE) != "#0B162A"

    def test_a_cell_with_its_own_contrast_keeps_its_own_edge(self):
        assert cell_edge("#D50A0A", LIGHT_SURFACE) == "#D50A0A"

    def test_history_ink_is_legible_on_its_own_fill(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                fill = mute_color(team, surface)
                assert contrast_ratio(history_ink(fill), fill) >= 3.0

    def test_history_ink_recedes_rather_than_shouting(self):
        """Deliberately softer than full contrast - history should recede."""
        fill = mute_color("#D50A0A", LIGHT_SURFACE)
        assert contrast_ratio(history_ink(fill), fill) < contrast_ratio(label_ink(fill), fill)


WK14_COUNTS = {(13, "TB"): 4, (14, "TB"): 16, (14, "CLE"): 2, (14, "SEA"): 1}
WK14_TOTALS = {13: 4, 14: 19}
WK14_COLORS = {"TB": "#D50A0A", "CLE": "#311D00", "SEA": "#002244"}
WK14_STATUS = {"TB": "lost", "CLE": "lost", "SEA": "won"}


def _grid(**kwargs):
    params = dict(
        weeks=[13, 14], rows=["TB", "CLE", "SEA"], counts=WK14_COUNTS,
        week_totals=WK14_TOTALS, team_colors=WK14_COLORS, current_week=14,
        background=LIGHT_SURFACE,
    )
    params.update(kwargs)
    return build_picks_grid(**params)


class TestEliminatedInFigure:
    """2025 week 14: 16 entrants on Tampa Bay, TB lost, the pool ended at one."""

    def test_omitting_team_status_changes_nothing(self):
        """Every existing caller and test must render exactly as before."""
        assert _grid().layout.shapes == _grid(team_status=None).layout.shapes

    def test_a_lost_current_week_cell_takes_the_eliminated_fill(self):
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert eliminated_fill("#D50A0A", LIGHT_SURFACE) in fills

    def test_a_won_current_week_cell_keeps_true_team_colour(self):
        """Won and not-yet-kicked-off are deliberately identical."""
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert "#002244" in fills

    def test_an_eliminated_teams_earlier_weeks_are_untouched(self):
        """History's job is volume, not outcome."""
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert mute_color("#D50A0A", LIGHT_SURFACE) in fills

    def test_a_lost_cell_takes_the_danger_border(self):
        shapes = _grid(team_status=WK14_STATUS).layout.shapes
        fill = eliminated_fill("#D50A0A", LIGHT_SURFACE)
        lost = [s for s in shapes if s["fillcolor"] == fill]
        assert lost and lost[0]["line"]["width"] == 2
        assert lost[0]["line"]["color"] == eliminated_edge(fill)

    def test_a_pending_team_is_not_treated_as_lost(self):
        status = {"TB": "pending", "CLE": "pending", "SEA": "pending"}
        fills = [s["fillcolor"] for s in _grid(team_status=status).layout.shapes]
        assert eliminated_fill("#D50A0A", LIGHT_SURFACE) not in fills

    def test_a_status_for_a_team_not_in_the_grid_is_ignored(self):
        _grid(team_status={"KC": "lost"})  # must not raise

    def test_the_tooltip_names_the_elimination(self):
        trace = _grid(team_status=WK14_STATUS).data[0]
        assert any("Eliminated" in text for text in trace.hovertext)


class TestContrastFill:
    """The current week's emphasis, lifted so the grid keeps leading with it.

    The grid's emphasis channel is bounded by team-colour-to-surface distance,
    so on #0B1220 a dark team has nowhere for its history to recede to: CIE76
    dE between CHI's current and muted cells falls to 3.5, about the
    just-noticeable threshold.
    """

    def test_a_team_that_already_clears_is_untouched(self):
        """Moves only as far as the floor requires."""
        assert contrast_fill("#FB4F14", DARK_SURFACE) == "#FB4F14"

    def test_dark_teams_are_lifted_on_a_dark_surface(self):
        for team in ("#0B162A", "#03202F", "#0C2340", "#203731"):
            lifted = contrast_fill(team, DARK_SURFACE)
            assert lifted != team
            assert contrast_ratio(lifted, DARK_SURFACE) >= 3.0

    def test_light_teams_are_darkened_on_a_light_surface(self):
        """Bidirectional. PIT gold and NO vegas gold fail on light and must
        come down; a lift-only version would run PIT to white."""
        for team in ("#FFB612", "#D3BC8D"):
            darkened = contrast_fill(team, LIGHT_SURFACE)
            assert relative_luminance(darkened) < relative_luminance(team)
            assert contrast_ratio(darkened, LIGHT_SURFACE) >= 3.0

    def test_every_team_clears_the_floor_on_both_surfaces(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                assert contrast_ratio(contrast_fill(team, surface), surface) >= 3.0

    def test_hue_is_preserved(self):
        """Lifting must not turn a team into a different team."""
        for team in ("#0B162A", "#203731", "#00338D"):
            assert abs(_to_hsl(contrast_fill(team, DARK_SURFACE))[0] - _to_hsl(team)[0]) < 0.02

    def test_a_black_team_lifts_to_grey(self):
        """LV #000000 has no hue to keep. Black cannot be shown on black; this
        is the accepted cost, not a bug to special-case back."""
        lifted = contrast_fill("#000000", DARK_SURFACE)
        r, g, b = _channels(lifted)
        assert r == g == b and r > 0

    def test_it_restores_the_emphasis_the_dark_surface_took_away(self):
        """The measurement that motivated it: CHI's current-vs-muted gap."""
        for team in ("#0B162A", "#03202F", "#000000", "#0C2340"):
            muted = mute_color(team, DARK_SURFACE)
            assert contrast_ratio(team, muted) < 1.6, "true colour barely separates"
            assert contrast_ratio(contrast_fill(team, DARK_SURFACE), muted) >= 2.5


class TestLiftedGridKeepsBothMutingAxes:
    """Lifting touches the current week only, so neither mute is disturbed."""

    def test_history_is_never_lifted(self):
        """Lifting history would close the gap the lift exists to open."""
        fig = _grid(background=DARK_SURFACE, current_week_min_contrast=3.0)
        fills = [s["fillcolor"] for s in fig.layout.shapes]
        assert mute_color("#D50A0A", DARK_SURFACE) in fills

    def test_elimination_still_mutes_on_saturation(self):
        fig = _grid(background=DARK_SURFACE, current_week_min_contrast=3.0,
                    team_status=WK14_STATUS)
        fills = [s["fillcolor"] for s in fig.layout.shapes]
        assert eliminated_fill("#D50A0A", DARK_SURFACE) in fills

    def test_an_eliminated_cell_is_not_lifted(self):
        """Elimination replaces the fill outright; it does not get emphasised."""
        fig = _grid(background=DARK_SURFACE, current_week_min_contrast=3.0,
                    team_status=WK14_STATUS)
        fills = [s["fillcolor"] for s in fig.layout.shapes]
        assert contrast_fill("#D50A0A", DARK_SURFACE) not in fills

    def test_zero_leaves_the_grid_at_true_team_colour(self):
        fig = _grid(background=DARK_SURFACE, current_week_min_contrast=0.0)
        assert "#D50A0A" in [s["fillcolor"] for s in fig.layout.shapes]
