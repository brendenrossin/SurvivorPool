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

    # Session B owns render_weekly_picks_chart and the live-scores call.
    # Everything else in main.py is this branch's.
    THEIRS = {"render_weekly_picks_chart"}

    def _my_functions(self):
        """Source of the top-level functions this branch owns.

        Resolved through the AST rather than by slicing on comment text, so it
        survives the other session restructuring the file around us.
        """
        import ast
        tree = ast.parse(self.SRC)
        return {
            node.name: ast.get_source_segment(self.SRC, node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name not in self.THEIRS
        }

    def test_no_module_opens_a_session(self):
        # Both sessions moved their reads behind cached functions, so nothing
        # in main.py should construct one any more.
        assert "SessionLocal()" not in self.SRC

    def test_no_emoji_in_the_functions_this_branch_owns(self):
        for name, source in self._my_functions().items():
            if name == "main":
                # main() still contains the live-scores call, which is theirs
                source = source.split("render_live_scores_widget")[0]
            offenders = sorted({ch for ch in source if ord(ch) >= 0x2500})
            assert not offenders, f"{name}: {offenders}"

    def test_kpi_row_carries_the_sparkline(self):
        assert "build_sparkline" in self.SRC


class TestInsightsTabsAreIsolated:
    """One panel raising must not take out the other three, and must say so
    rather than surfacing a traceback."""

    SRC = open("app/main.py").read()

    def test_each_panel_render_is_guarded(self):
        assert "render(SEASON)" in self.SRC
        assert "is unavailable right now" in self.SRC

    def test_failure_is_logged_with_the_panel_name(self):
        assert 'logging.exception("%s failed to render", name)' in self.SRC


class TestNoUndefinedNames:
    """A NameError gate.

    This bug class has bitten this project twice in one day: a missing import
    killed all four Pool Insights tabs while each printed its empty-state
    message, so a dead feature looked exactly like an empty pool; and a
    constant renamed on one branch left three live references in a region the
    suite never executes.

    Scoped to undefined names only - not unused imports - so it stays a
    zero-false-positive correctness gate rather than a style checker.
    """

    def test_app_package_has_no_undefined_names(self):
        import pathlib
        import subprocess
        import sys

        files = sorted(str(p) for p in pathlib.Path("app").glob("*.py"))
        result = subprocess.run(
            [sys.executable, "-m", "pyflakes", *files],
            capture_output=True, text=True,
        )
        undefined = [
            line for line in result.stdout.splitlines()
            if "undefined name" in line
        ]
        assert not undefined, "\n".join(undefined)
