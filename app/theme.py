"""
Design tokens and contrast maths.

Single source of truth for every colour in the app. Both palettes are defined
and selected by one switch, so a light/dark reversal is one line and no
component holds a surface literal.

The colour maths (relative_luminance, label_ink, mute_color) is imported from
picks_grid rather than copied. The backlog records that theme tokens are already
forked between picks_grid and mobile_plotly_config, and that the white-on-white
hover bug was consequently fixed twice in two places. This is not a third fork.
"""

import colorsys
from typing import Dict, Tuple

from app.picks_grid import relative_luminance, label_ink, mute_color  # noqa: F401

PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "SURFACE": "#0B1220",
        "SURFACE_RAISED": "#141E33",
        "INK": "#E8EDF7",
        "INK_MUTED": "#8A97AE",
        "BORDER": "#24304A",
        "DANGER": "#EF4444",
        "WIN": "#34D399",
        "PENDING": "#94A3B8",
        "ACCENT": "#F59E0B",
    },
    "light": {
        "SURFACE": "#F8FAFC",
        "SURFACE_RAISED": "#FFFFFF",
        "INK": "#0F172A",
        "INK_MUTED": "#5B6880",
        "BORDER": "#D8DFEA",
        "DANGER": "#B91C1C",
        "WIN": "#047857",
        "PENDING": "#5B6880",
        "ACCENT": "#B45309",
    },
}

# The one switch. Flipping this reverses the whole app.
ACTIVE = "dark"

SURFACE = PALETTES[ACTIVE]["SURFACE"]
SURFACE_RAISED = PALETTES[ACTIVE]["SURFACE_RAISED"]
INK = PALETTES[ACTIVE]["INK"]
INK_MUTED = PALETTES[ACTIVE]["INK_MUTED"]
BORDER = PALETTES[ACTIVE]["BORDER"]
DANGER = PALETTES[ACTIVE]["DANGER"]
WIN = PALETTES[ACTIVE]["WIN"]
PENDING = PALETTES[ACTIVE]["PENDING"]
ACCENT = PALETTES[ACTIVE]["ACCENT"]

FONT_STACK = "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"


def _channels(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _to_hex(rgb_floats) -> str:
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, int(round(v * 255)))) for v in rgb_floats
    )


def contrast_ratio(a: str, b: str) -> float:
    """WCAG relative contrast between two hex colours."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def contrast_fill(color: str, background: str, target: float = 3.0,
                  steps: int = 200) -> str:
    """Move a fill's lightness until it clears `target` against `background`.

    Hue and saturation are preserved, so team identity survives - only the
    lightness moves, and only as far as it must.

    Direction depends on the surface, which is why this is not called "lift":
    on the dark surface 22 of 32 team colours fail and must go up (GB #203731
    is 1.47:1); on the light surface PIT and NO fail and must come DOWN. A
    lift-only implementation runs PIT to white.

    Two uses, both deliberate:

    - Marks that FLOAT on the surface - bars with no border - where legibility
      is entirely fill-vs-surface contrast.
    - The picks grid's CURRENT WEEK, where the job is emphasis rather than
      legibility: history mutes toward the surface, so a team whose colour is
      already surface-adjacent has nowhere to separate to. Never applied to
      history, which must keep muting on lightness alone.

    A bounded mark's legibility never depends on this - it carries a hairline
    and contrast-derived ink, and keeps its true team colour.
    """
    if contrast_ratio(color, background) >= target:
        return color

    r, g, b = _channels(color)
    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    lighten = relative_luminance(background) < 0.5

    for i in range(1, steps + 1):
        step = i / steps
        new_l = (
            lightness + (1.0 - lightness) * step if lighten
            else lightness * (1 - step)
        )
        candidate = _to_hex(colorsys.hls_to_rgb(hue, new_l, saturation))
        if contrast_ratio(candidate, background) >= target:
            return candidate

    return "#FFFFFF" if lighten else "#000000"


GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"] {{
  font-family: {FONT_STACK};
}}

.stApp {{ background-color: {SURFACE}; color: {INK}; }}
.main .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1160px; }}

h1, h2, h3 {{ letter-spacing: -0.02em; color: {INK}; }}
h1 {{ font-weight: 800; font-size: 1.9rem; }}

/* Section eyebrow - what the emoji headings became */
.eyebrow {{
  font-size: .72rem; font-weight: 700; letter-spacing: .14em;
  text-transform: uppercase; color: {INK_MUTED}; margin: 0 0 .4rem 0;
}}

.card {{
  background: {SURFACE_RAISED};
  border: 1px solid {BORDER};
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 14px;
}}

.kpi-label {{
  font-size: .72rem; font-weight: 700; letter-spacing: .12em;
  text-transform: uppercase; color: {INK_MUTED};
}}
.kpi-value {{
  font-size: 2.6rem; font-weight: 800; line-height: 1.05; color: {INK};
  font-variant-numeric: tabular-nums;
}}
.kpi-sub {{ font-size: .82rem; color: {INK_MUTED}; }}

/* Text badges - what the status emoji became */
.badge {{
  display: inline-block; padding: .16rem .5rem; border-radius: 6px;
  font-size: .68rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; border: 1px solid currentColor;
}}
.badge.danger  {{ color: {DANGER}; }}
.badge.win     {{ color: {WIN}; }}
.badge.pending {{ color: {PENDING}; }}

.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{
  background: transparent; padding: .5rem .9rem; border-radius: 8px 8px 0 0;
  font-weight: 600; color: {INK_MUTED};
}}
.stTabs [aria-selected="true"] {{ color: {INK}; border-bottom: 2px solid {ACCENT}; }}

.js-plotly-plot, .stPlotlyChart {{ border-radius: 12px; overflow: hidden; }}
</style>
"""
