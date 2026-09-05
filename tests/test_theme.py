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
