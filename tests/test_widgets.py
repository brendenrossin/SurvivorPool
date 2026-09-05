"""The four Pool Insights widgets, as pure view code."""

import inspect

import pytest

from app import chaos_meter, graveyard, survivors, team_of_doom

MODULES = [team_of_doom, graveyard, survivors, chaos_meter]
RENDERERS = [
    (team_of_doom, "render_team_of_doom_widget"),
    (graveyard, "render_graveyard_widget"),
    (survivors, "render_survivors_widget"),
    (chaos_meter, "render_chaos_meter_widget"),
]


class TestNoDatabaseAccessInViews:
    """Every @st.cache_* in app/ lives in dashboard_data. These modules used to
    open a session and query on every script run, and st.tabs executes all four
    bodies every time."""

    @pytest.mark.parametrize("module", MODULES)
    def test_module_never_opens_a_session(self, module):
        src = inspect.getsource(module)
        assert "SessionLocal" not in src
        assert "db.query" not in src

    @pytest.mark.parametrize("module,name", RENDERERS)
    def test_render_takes_season_only(self, module, name):
        params = list(inspect.signature(getattr(module, name)).parameters)
        assert params == ["season"]


class TestDeadCodeRemoved:
    @pytest.mark.parametrize("module,name", [
        (graveyard, "render_memorial_wall"),
        (graveyard, "render_graveyard_timeline"),
        (team_of_doom, "render_doom_details"),
        (survivors, "render_survivor_timeline"),
        (survivors, "get_eliminated_count"),
        (chaos_meter, "render_chaos_explanation"),
        (chaos_meter, "render_weekly_chaos_summary"),
        (chaos_meter, "calculate_elimination_percentage"),
    ])
    def test_is_gone(self, module, name):
        assert not hasattr(module, name)


class TestNoEmoji:
    @pytest.mark.parametrize("module", MODULES)
    def test_source_carries_no_emoji(self, module):
        src = inspect.getsource(module)
        offenders = sorted({ch for ch in src if ord(ch) >= 0x2500})
        assert not offenders, f"{module.__name__}: {offenders}"


class TestDoomFigure:
    ROWS = [
        {"team": "GB", "eliminations": 73, "first_week": 3},
        {"team": "LAC", "eliminations": 32, "first_week": 4},
    ]
    COLORS = {"GB": "#203731", "LAC": "#0080C6"}

    def test_one_bar_per_team(self):
        fig = team_of_doom.build_doom_figure(self.ROWS, self.COLORS)
        assert len(fig.data[0].x) == 2

    def test_every_bar_clears_the_contrast_floor(self):
        # GB #203731 is 1.47:1 on the dark surface untreated
        from app.theme import SURFACE, contrast_ratio
        fig = team_of_doom.build_doom_figure(self.ROWS, self.COLORS)
        for color in fig.data[0].marker.color:
            assert contrast_ratio(color, SURFACE) >= 3.0

    def test_bars_are_ordered_with_the_largest_last(self):
        # plotly draws horizontal bars bottom-up, so the rank leader is last
        fig = team_of_doom.build_doom_figure(self.ROWS, self.COLORS)
        assert list(fig.data[0].y)[-1] == "GB"

    def test_unknown_team_gets_a_fallback_not_a_crash(self):
        fig = team_of_doom.build_doom_figure(
            [{"team": "ZZZ", "eliminations": 1, "first_week": 1}], {})
        assert len(fig.data[0].x) == 1

    def test_caps_at_the_top_n(self):
        many = [{"team": f"T{i}", "eliminations": i, "first_week": 1}
                for i in range(30)]
        fig = team_of_doom.build_doom_figure(many, {})
        assert len(fig.data[0].x) == team_of_doom.TOP_N

    def test_empty_rows_gives_an_empty_figure(self):
        assert team_of_doom.build_doom_figure([], {}).data == ()


class TestGraveyardBars:
    ROWS = [
        {"week": 1, "player": "A", "team": "MIA"},
        {"week": 3, "player": "B", "team": "ATL"},
        {"week": 3, "player": "C", "team": "ATL"},
    ]

    def test_counts_eliminations_per_week(self):
        fig = graveyard.build_elimination_bars(self.ROWS)
        assert list(fig.data[0].x) == [1, 3]
        assert list(fig.data[0].y) == [1, 2]

    def test_empty_rows_gives_an_empty_figure(self):
        assert graveyard.build_elimination_bars([]).data == ()


class TestMainWiring:
    SRC = open("app/main.py").read()

    def test_donut_is_gone(self):
        assert "render_remaining_players_donut" not in self.SRC
        assert "go.Pie" not in self.SRC

    def test_no_inline_css_block_remains(self):
        # The !important wall existed to fight Streamlit's light base. The base
        # is now set in .streamlit/config.toml, so it can be deleted.
        assert "@import url" not in self.SRC
        assert "!important" not in self.SRC

    def test_surface_comes_from_theme(self):
        assert "APP_SURFACE" not in self.SRC
        assert "from app.theme import" in self.SRC

    def test_meme_rendering_moved_out(self):
        assert "def render_meme_stats" not in self.SRC
        assert "from app.meme_cards import render_meme_stats" in self.SRC

    def _my_regions(self):
        """main.py minus Session B's territory: the live-scores block and
        render_weekly_picks_chart (which includes the breakdown table)."""
        src = self.SRC
        live_start = src.index("    # Live Scores Widget")
        live_end = src.index("    st.divider()", live_start)
        grid_start = src.index("def render_weekly_picks_chart")
        grid_end = src.index("def render_player_search")
        return src[:live_start] + src[live_end:grid_start] + src[grid_end:]

    def test_insights_tabs_open_no_sessions(self):
        # Both remaining SessionLocal() calls are Session B's - live scores and
        # the breakdown table. Nothing this branch owns opens one.
        assert "SessionLocal()" not in self._my_regions()

    def test_widgets_are_called_without_a_db_handle(self):
        for name in ("render_team_of_doom_widget", "render_survivors_widget",
                     "render_graveyard_widget", "render_chaos_meter_widget"):
            assert f"{name}(SEASON)" in self.SRC

    def test_kpi_row_carries_the_sparkline(self):
        assert "build_sparkline" in self.SRC

    def test_no_emoji_in_ui_copy_this_branch_owns(self):
        # page_icon is the browser tab icon, not UI copy, and the startup
        # prints go to Railway logs - both stay.
        mine = self._my_regions()
        for skip in ('page_icon="\U0001F3C8",',
                     'print("\U0001F680 Starting Survivor Pool Dashboard...")',
                     'print("\u2705 Streamlit app starting...")'):
            mine = mine.replace(skip, "")
        offenders = sorted({ch for ch in mine if ord(ch) >= 0x2500})
        assert not offenders, offenders
