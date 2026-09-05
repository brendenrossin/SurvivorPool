"""Design tokens and contrast maths."""

import colorsys
import json

import pytest

from app import theme

TEAMS = json.load(open("db/seed_team_map.json"))["teams"]
ALL_COLORS = [d["color"] for d in TEAMS.values()]


def _hue(hex_color):
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)[0]


class TestContrastRatio:
    def test_identical_colors_are_one_to_one(self):
        assert theme.contrast_ratio("#123456", "#123456") == pytest.approx(1.0)

    def test_black_on_white_is_21_to_1(self):
        assert theme.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.1)

    def test_is_symmetric(self):
        assert theme.contrast_ratio("#0B1220", "#FFB612") == pytest.approx(
            theme.contrast_ratio("#FFB612", "#0B1220")
        )


class TestContrastFill:
    @pytest.mark.parametrize("background", ["#0B1220", "#F8FAFC"])
    def test_every_team_clears_the_floor_on_both_surfaces(self, background):
        for color in ALL_COLORS:
            out = theme.contrast_fill(color, background)
            assert theme.contrast_ratio(out, background) >= 3.0, f"{color} on {background}"

    def test_leaves_a_passing_color_untouched(self):
        assert theme.contrast_fill("#FFB612", "#0B1220") == "#FFB612"

    def test_lightens_on_a_dark_surface(self):
        out = theme.contrast_fill("#203731", "#0B1220")  # GB, 1.47:1
        assert theme.relative_luminance(out) > theme.relative_luminance("#203731")

    def test_darkens_on_a_light_surface(self):
        # PIT fails on light and must go DOWN. A lift-only implementation runs
        # it to white; this test is what catches that.
        out = theme.contrast_fill("#FFB612", "#F8FAFC")
        assert theme.relative_luminance(out) < theme.relative_luminance("#FFB612")

    def test_preserves_hue(self):
        out = theme.contrast_fill("#203731", "#0B1220")
        assert _hue(out) == pytest.approx(_hue("#203731"), abs=0.02)

    def test_is_idempotent(self):
        once = theme.contrast_fill("#203731", "#0B1220")
        assert theme.contrast_fill(once, "#0B1220") == once

    def test_black_on_black_still_returns_something_visible(self):
        out = theme.contrast_fill("#000000", "#0B1220")
        assert theme.contrast_ratio(out, "#0B1220") >= 3.0

    def test_moves_only_as_far_as_it_must(self):
        # GB should land just over the floor, not run to white
        out = theme.contrast_fill("#203731", "#0B1220")
        assert theme.contrast_ratio(out, "#0B1220") < 4.0


class TestTokens:
    TOKEN_NAMES = ("SURFACE", "SURFACE_RAISED", "INK", "INK_MUTED",
                   "BORDER", "DANGER", "WIN", "PENDING", "ACCENT")

    @pytest.mark.parametrize("name", TOKEN_NAMES)
    def test_token_is_a_hex_string(self, name):
        value = getattr(theme, name)
        assert isinstance(value, str) and value.startswith("#")

    def test_both_palettes_define_the_same_keys(self):
        assert set(theme.PALETTES["light"]) == set(theme.PALETTES["dark"])

    def test_ink_is_readable_on_surface(self):
        assert theme.contrast_ratio(theme.INK, theme.SURFACE) >= 4.5

    def test_muted_ink_clears_the_large_text_floor(self):
        assert theme.contrast_ratio(theme.INK_MUTED, theme.SURFACE) >= 3.0

    @pytest.mark.parametrize("name", ("DANGER", "WIN", "PENDING", "ACCENT"))
    def test_semantic_colors_are_visible_on_their_surface(self, name):
        for palette in theme.PALETTES.values():
            assert theme.contrast_ratio(palette[name], palette["SURFACE"]) >= 3.0

    def test_danger_differs_between_palettes(self):
        # #B91C1C is right on light and too dark on the slate surface
        assert theme.PALETTES["light"]["DANGER"] != theme.PALETTES["dark"]["DANGER"]

    def test_global_css_carries_no_opposite_palette_literal(self):
        other = "light" if theme.ACTIVE == "dark" else "dark"
        assert theme.PALETTES[other]["SURFACE"] not in theme.GLOBAL_CSS

    def test_global_css_paints_the_app_background(self):
        assert theme.SURFACE in theme.GLOBAL_CSS


class TestMobileConfigTokens:
    """The shared Plotly layer. Every render_mobile_chart call site is in a
    file this branch owns; the picks grid bypasses it entirely."""

    def test_no_hardcoded_light_ink_remains(self):
        src = open("app/mobile_plotly_config.py").read()
        assert "#0F172A" not in src
        assert '"white"' not in src

    def test_layout_ink_is_readable_on_the_active_surface(self):
        from app import mobile_plotly_config as mpc
        layout = mpc.get_mobile_layout("bar_chart")
        assert theme.contrast_ratio(layout["font"]["color"], theme.SURFACE) >= 4.5

    def test_axis_ink_clears_the_large_text_floor(self):
        from app import mobile_plotly_config as mpc
        layout = mpc.get_mobile_layout("bar_chart")
        tick = layout["xaxis"]["tickfont"]["color"]
        assert theme.contrast_ratio(tick, theme.SURFACE) >= 3.0

    def test_hover_label_sets_both_background_and_ink(self):
        # The bug this guards: an earlier version set no font colour at all and
        # Plotly's auto-contrast rendered white on white. Re-tokenize, never revert.
        import plotly.graph_objects as go
        from app import mobile_plotly_config as mpc
        fig = go.Figure(go.Bar(x=[1], y=[1]))
        mpc.apply_mobile_optimization(fig, "bar_chart")
        hover = fig.data[0].hoverlabel
        assert hover.bgcolor is not None
        assert hover.font.color is not None
        assert theme.contrast_ratio(hover.font.color, hover.bgcolor) >= 4.5

    def test_get_mobile_layout_returns_a_copy(self):
        # Callers mutate the returned dict; a shared reference would leak
        # one chart's height into the next.
        from app import mobile_plotly_config as mpc
        first = mpc.get_mobile_layout("bar_chart")
        first["height"] = 999
        assert "height" not in mpc.get_mobile_layout("bar_chart")

    def test_dead_helpers_are_gone(self):
        from app import mobile_plotly_config as mpc
        assert not hasattr(mpc, "create_touch_annotation")
        assert not hasattr(mpc, "MOBILE_COLORS")
        assert not hasattr(mpc, "get_mobile_color_scheme")

    def test_gauge_and_donut_configs_removed(self):
        from app import mobile_plotly_config as mpc
        assert "gauge" not in mpc.CHART_CONFIGS
        assert "donut" not in mpc.CHART_CONFIGS


class TestModulesImportCleanly:
    """A guard against exactly the breakage that deleting a shared helper
    causes: the test suite never imports app.main, so an ImportError there
    ships silently."""

    @pytest.mark.parametrize("module", [
        "app.main", "app.theme", "app.mobile_plotly_config",
        "app.graveyard", "app.survivors", "app.team_of_doom", "app.chaos_meter",
    ])
    def test_module_imports(self, module):
        import importlib
        importlib.import_module(module)
