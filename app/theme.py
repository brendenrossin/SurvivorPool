"""
Design tokens and contrast maths.

Single source of truth for every colour in the app. Both palettes are defined
and selected by one switch, so a light/dark reversal is one line and no
component holds a surface literal.

All colour maths is imported from picks_grid rather than copied. The backlog
records that theme tokens were already forked between picks_grid and
mobile_plotly_config, and that the white-on-white hover bug was consequently
fixed twice in two places. This is not a third fork.

contrast_fill lives there because picks_grid merged first and cannot import a
module that did not yet exist on staging. It is re-exported here so callers
have one place to import colour from.
"""

from typing import Dict

from app.picks_grid import (
    contrast_fill,
    contrast_ratio,
    label_ink,
    mute_color,
    relative_luminance,
)

# Re-exported so callers have one place to import colour from.
__all__ = [
    "contrast_fill", "contrast_ratio", "label_ink", "mute_color",
    "relative_luminance", "PALETTES", "ACTIVE", "GLOBAL_CSS", "FONT_STACK",
    "SURFACE", "SURFACE_RAISED", "INK", "INK_MUTED", "BORDER",
    "DANGER", "WIN", "PENDING", "ACCENT",
]

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

/* Two levels, so a section reads as bigger than a panel inside it.
   Both replace emoji headings. */
.section-title {{
  font-size: 1.05rem; font-weight: 700; letter-spacing: -.01em;
  color: {INK}; margin: .2rem 0 .9rem 0;
}}
.eyebrow {{
  font-size: .72rem; font-weight: 700; letter-spacing: .14em;
  text-transform: uppercase; color: {INK_MUTED}; margin: 1.4rem 0 .4rem 0;
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
/* Bottom rhythm matters most on a phone, where the three KPI
   columns stack into one and would otherwise run together. */
.kpi-sub {{ font-size: .82rem; color: {INK_MUTED}; margin-bottom: 1.4rem; }}

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

/* Scoreboard cards. Only the live-scores widget uses a bordered container,
   and four to a row leaves each one narrow, so the default padding is most of
   the card. */
[data-testid="stVerticalBlockBorderWrapper"] > div {{ padding: .55rem .7rem; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 10px; }}
[data-testid="stVerticalBlockBorderWrapper"] p {{ margin-bottom: .15rem; }}
</style>
"""
