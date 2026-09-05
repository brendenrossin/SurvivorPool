# Plots & Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the donut, meme tables and four Pool Insights widgets with a coherent broadcast-dark visual language, and move every widget's database access into cached functions.

**Architecture:** Three new pure-logic modules (`theme`, `attrition`, `meme_cards`) hold all colour maths and figure construction with no database access. Four cached query functions in `dashboard_data.py` become the only place widgets touch Postgres, so `render_*` functions drop their `db` parameter and become pure view code. Every colour resolves through a token switch so a light/dark reversal is one line.

**Tech Stack:** Streamlit 1.50.0, Plotly `graph_objects`, SQLAlchemy, PostgreSQL, Python 3.11.14

**Spec:** `docs/design/plots-overhaul-spec.md`

## Global Constraints

- **Never edit** `app/live_scores.py`, `app/picks_grid.py`, or the `render_weekly_picks_chart` / live-scores regions of `app/main.py`. Session B owns them.
- **Every database read** is `@st.cache_data(ttl=60)` and closes its session in a `finally`. CLAUDE.md convention.
- **Never render picks for a week that has not kicked off.** The sheet holds future weeks.
- **No emoji** in headings, labels, or row decoration. Status becomes a colour-coded text badge.
- **No colour literals in component code.** Everything resolves through `app/theme.py`.
- **Mobile-first:** every chart must survive a 390px viewport.
- Run tests with: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
- Local run against real data:
  `export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"` then
  `NFL_SEASON=2025 PYTHONPATH=. .venv/bin/streamlit run app/main.py`.
  **This is the production database. Read-only. Never write to it.**
- The venv is at `/Users/brentrossin/Side_Projects/SurvivorPool/.venv` (Python 3.11.14).
- 60 tests pass at branch point. That number must not go down.

---

## File Structure

| File | Responsibility | DB |
|---|---|---|
| `.streamlit/config.toml` | Streamlit base theme | — |
| `app/theme.py` | Tokens, `contrast_fill`, `GLOBAL_CSS` | none |
| `app/attrition.py` | Attrition sparkline + full curve figures | none |
| `app/meme_cards.py` | Ranked meme card rendering | none |
| `app/dashboard_data.py` | All queries, all caching | all |
| `app/team_of_doom.py` | View only | none |
| `app/graveyard.py` | View only | none |
| `app/survivors.py` | View only | none |
| `app/chaos_meter.py` | View only | none |
| `app/mobile_plotly_config.py` | Shared Plotly layout, re-tokenized | none |
| `app/main.py` | Wiring | none |

---

### Task 1: Theme tokens and `contrast_fill`

**Files:**
- Create: `app/theme.py`
- Create: `.streamlit/config.toml`
- Test: `tests/test_theme.py`

**Interfaces:**
- Consumes: `relative_luminance`, `label_ink`, `mute_color` from `app.picks_grid` (import only — never edit that file)
- Produces: `SURFACE`, `SURFACE_RAISED`, `INK`, `INK_MUTED`, `BORDER`, `DANGER`, `WIN`, `PENDING`, `ACCENT` (all `str` hex); `contrast_fill(color: str, background: str, target: float = 3.0) -> str`; `contrast_ratio(a: str, b: str) -> float`; `GLOBAL_CSS: str`; `PALETTES: dict`; `ACTIVE: str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_theme.py
import json
import pytest
from app import theme

TEAMS = json.load(open("db/seed_team_map.json"))["teams"]
ALL_COLORS = [d["color"] for d in TEAMS.values()]


class TestContrastRatio:
    def test_identical_colors_are_one_to_one(self):
        assert theme.contrast_ratio("#123456", "#123456") == pytest.approx(1.0)

    def test_black_on_white_is_21_to_1(self):
        assert theme.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.1)

    def test_is_symmetric(self):
        a = theme.contrast_ratio("#0B1220", "#FFB612")
        b = theme.contrast_ratio("#FFB612", "#0B1220")
        assert a == pytest.approx(b)


class TestContrastFill:
    @pytest.mark.parametrize("background", ["#0B1220", "#F8FAFC"])
    def test_every_team_clears_the_floor_on_both_surfaces(self, background):
        for color in ALL_COLORS:
            out = theme.contrast_fill(color, background)
            assert theme.contrast_ratio(out, background) >= 3.0, f"{color} on {background}"

    def test_leaves_a_passing_color_untouched(self):
        # PIT #FFB612 already clears 3:1 on the dark surface
        assert theme.contrast_fill("#FFB612", "#0B1220") == "#FFB612"

    def test_lightens_on_a_dark_surface(self):
        out = theme.contrast_fill("#203731", "#0B1220")  # GB, 1.47:1
        assert theme.relative_luminance(out) > theme.relative_luminance("#203731")

    def test_darkens_on_a_light_surface(self):
        # PIT fails on light and must go DOWN, not up. A lift-only
        # implementation runs it to white and this test catches that.
        out = theme.contrast_fill("#FFB612", "#F8FAFC")
        assert theme.relative_luminance(out) < theme.relative_luminance("#FFB612")

    def test_preserves_hue(self):
        import colorsys
        src = "#203731"
        out = theme.contrast_fill(src, "#0B1220")
        def hue(h):
            r, g, b = (int(h.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4))
            return colorsys.rgb_to_hls(r, g, b)[0]
        assert hue(out) == pytest.approx(hue(src), abs=0.02)

    def test_is_idempotent(self):
        once = theme.contrast_fill("#203731", "#0B1220")
        assert theme.contrast_fill(once, "#0B1220") == once

    def test_black_on_black_still_returns_something_visible(self):
        out = theme.contrast_fill("#000000", "#0B1220")
        assert theme.contrast_ratio(out, "#0B1220") >= 3.0


class TestTokens:
    def test_active_palette_is_complete(self):
        for name in ("SURFACE", "SURFACE_RAISED", "INK", "INK_MUTED",
                     "BORDER", "DANGER", "WIN", "PENDING", "ACCENT"):
            assert isinstance(getattr(theme, name), str)
            assert getattr(theme, name).startswith("#")

    def test_both_palettes_define_the_same_keys(self):
        assert set(theme.PALETTES["light"]) == set(theme.PALETTES["dark"])

    def test_ink_is_readable_on_surface(self):
        assert theme.contrast_ratio(theme.INK, theme.SURFACE) >= 4.5

    def test_muted_ink_still_clears_the_large_text_floor(self):
        assert theme.contrast_ratio(theme.INK_MUTED, theme.SURFACE) >= 3.0

    def test_danger_differs_between_palettes(self):
        # #B91C1C is right on light, too dark on the slate surface
        assert theme.PALETTES["light"]["DANGER"] != theme.PALETTES["dark"]["DANGER"]

    def test_global_css_carries_no_light_literal_when_dark_is_active(self):
        if theme.ACTIVE == "dark":
            assert "#F8FAFC" not in theme.GLOBAL_CSS
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_theme.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.theme'`

- [ ] **Step 3: Write `app/theme.py`**

```python
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
from typing import Dict

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
        "PENDING": "#64748B",
        "ACCENT": "#B45309",
    },
}

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


def _rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb_floats) -> str:
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, int(round(v * 255)))) for v in rgb_floats
    )


def contrast_ratio(a: str, b: str) -> float:
    """WCAG relative-contrast ratio between two hex colours."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def contrast_fill(color: str, background: str, target: float = 3.0,
                  steps: int = 200) -> str:
    """Adjust a fill's lightness until it clears `target` against `background`.

    Hue and saturation are preserved, so team identity survives - only the
    lightness moves, and only as far as it must.

    Direction depends on the surface, which is why this is not "lift": on the
    dark surface 22 of 32 team colours fail and must go up (GB #203731 is
    1.47:1); on the light surface PIT and NO fail and must come DOWN. A
    lift-only implementation runs PIT to white.

    This is for marks that FLOAT on the surface - bars with no border. A
    bounded mark (a grid cell) carries a hairline and contrast-derived ink, so
    its legibility never depends on fill-vs-surface contrast and it must keep
    its true team colour. Do not apply this to the picks grid.
    """
    if contrast_ratio(color, background) >= target:
        return color

    r, g, b = _rgb(color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    lighten = relative_luminance(background) < 0.5

    for i in range(1, steps + 1):
        step = i / steps
        new_l = l + (1.0 - l) * step if lighten else l * (1 - step)
        candidate = _hex(colorsys.hls_to_rgb(h, new_l, s))
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
h1 {{ font-weight: 800; }}

/* Section eyebrow - replaces the emoji headings */
.eyebrow {{
  font-size: .72rem; font-weight: 700; letter-spacing: .14em;
  text-transform: uppercase; color: {INK_MUTED}; margin: 0 0 .5rem 0;
}}

.card {{
  background: {SURFACE_RAISED};
  border: 1px solid {BORDER};
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 14px;
}}

/* KPI */
.kpi-label {{ font-size: .72rem; font-weight: 700; letter-spacing: .12em;
              text-transform: uppercase; color: {INK_MUTED}; }}
.kpi-value {{ font-size: 2.6rem; font-weight: 800; line-height: 1.05;
              color: {INK}; font-variant-numeric: tabular-nums; }}
.kpi-sub   {{ font-size: .82rem; color: {INK_MUTED}; }}

/* Text badges - what the status emoji became */
.badge {{
  display:inline-block; padding:.16rem .5rem; border-radius:6px;
  font-size:.68rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; border:1px solid currentColor;
}}
.badge.danger  {{ color:{DANGER}; }}
.badge.win     {{ color:{WIN}; }}
.badge.pending {{ color:{PENDING}; }}

.stTabs [data-baseweb="tab-list"] {{ gap: .4rem; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{
  background: transparent; padding: .5rem .9rem; border-radius: 8px 8px 0 0;
  font-weight: 600; color: {INK_MUTED};
}}
.stTabs [aria-selected="true"] {{ color: {INK}; border-bottom: 2px solid {ACCENT}; }}

.js-plotly-plot, .stPlotlyChart {{ border-radius: 12px; overflow: hidden; }}
</style>
"""
```

- [ ] **Step 4: Write `.streamlit/config.toml`**

Setting the base means Streamlit's own widgets render dark natively, so `main.py`'s
`!important` overrides get deleted in Task 9 rather than extended.

```toml
[theme]
base = "dark"
primaryColor = "#F59E0B"
backgroundColor = "#0B1220"
secondaryBackgroundColor = "#141E33"
textColor = "#E8EDF7"
font = "sans serif"

[server]
headless = true
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_theme.py -q`
Expected: PASS, all tests

- [ ] **Step 6: Commit**

```bash
git add app/theme.py tests/test_theme.py .streamlit/config.toml
git commit -m "Add design tokens and bidirectional contrast_fill"
```

---

### Task 2: Re-tokenize the shared Plotly layer

**Files:**
- Modify: `app/mobile_plotly_config.py`
- Test: `tests/test_theme.py` (append)

**Interfaces:**
- Consumes: `app.theme` tokens
- Produces: unchanged public API — `get_mobile_config()`, `get_mobile_layout(chart_type)`, `apply_mobile_optimization(fig, chart_type)`, `render_mobile_chart(fig, chart_type)`

All six `render_mobile_chart` call sites are in files this branch owns; the picks grid
bypasses this module entirely, so nothing here reaches Session B.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_theme.py
from app import mobile_plotly_config as mpc


class TestMobileConfigTokens:
    def test_no_hardcoded_light_ink_remains(self):
        src = open("app/mobile_plotly_config.py").read()
        assert "#0F172A" not in src
        assert '"white"' not in src

    def test_layout_ink_is_readable_on_the_active_surface(self):
        layout = mpc.get_mobile_layout("bar_chart")
        assert theme.contrast_ratio(layout["font"]["color"], theme.SURFACE) >= 4.5

    def test_hover_label_sets_both_background_and_ink(self):
        # The bug this guards: an earlier version set no font colour at all and
        # Plotly's auto-contrast rendered white on white. Re-tokenize, never revert.
        import plotly.graph_objects as go
        fig = go.Figure(go.Bar(x=[1], y=[1]))
        mpc.apply_mobile_optimization(fig, "bar_chart")
        hl = fig.data[0].hoverlabel
        assert hl.bgcolor is not None and hl.font.color is not None
        assert theme.contrast_ratio(hl.font.color, hl.bgcolor) >= 4.5

    def test_dead_helpers_are_gone(self):
        assert not hasattr(mpc, "create_touch_annotation")
        assert not hasattr(mpc, "MOBILE_COLORS")
        assert not hasattr(mpc, "get_mobile_color_scheme")

    def test_gauge_config_removed(self):
        assert "gauge" not in mpc.CHART_CONFIGS
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_theme.py -q -k Mobile`
Expected: FAIL — `#0F172A` still present, `create_touch_annotation` still defined

- [ ] **Step 3: Rewrite `app/mobile_plotly_config.py`**

```python
"""
Shared Plotly configuration.

Every layout value resolves through app.theme, so a surface change reaches every
chart that routes through render_mobile_chart. The picks grid deliberately does
NOT route through here - it calls st.plotly_chart directly because CHART_CONFIGS
would clobber its computed height and axis config - so it needs its own pass and
is Session B's to make.
"""

from app.theme import (
    SURFACE_RAISED, INK, INK_MUTED, BORDER, FONT_STACK,
)

MOBILE_CONFIG = {
    'displayModeBar': False,
    'displaylogo': False,
    'doubleClick': 'reset',
    'scrollZoom': False,
    'responsive': True,
    'staticPlot': False,
}

_AXIS = {
    'tickfont': {'size': 11, 'color': INK_MUTED},
    'title': {'font': {'size': 11, 'color': INK_MUTED}},
    'gridcolor': BORDER,
    'linecolor': BORDER,
    'zerolinecolor': BORDER,
}

MOBILE_LAYOUT_DEFAULTS = {
    'margin': {'l': 8, 'r': 8, 't': 8, 'b': 28},
    'font': {'family': FONT_STACK, 'size': 12, 'color': INK},
    'showlegend': False,
    'hovermode': 'closest',
    'dragmode': False,
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'plot_bgcolor': 'rgba(0,0,0,0)',
}

CHART_CONFIGS = {
    'bar_chart': {**MOBILE_LAYOUT_DEFAULTS, 'xaxis': _AXIS, 'yaxis': _AXIS},
    'line_chart': {**MOBILE_LAYOUT_DEFAULTS, 'xaxis': _AXIS, 'yaxis': _AXIS},
    'sparkline': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 44,
        'margin': {'l': 0, 'r': 0, 't': 2, 'b': 2},
        'xaxis': {'visible': False},
        'yaxis': {'visible': False},
    },
}


def get_mobile_config():
    """Plotly interaction config, shared by every chart including the grid."""
    return MOBILE_CONFIG


def get_mobile_layout(chart_type='default'):
    return dict(CHART_CONFIGS.get(chart_type, MOBILE_LAYOUT_DEFAULTS))


def apply_mobile_optimization(fig, chart_type='default'):
    """Apply shared layout and a legible tooltip."""
    fig.update_layout(**get_mobile_layout(chart_type))
    fig.update_traces(
        hoverlabel=dict(
            bgcolor=SURFACE_RAISED,
            bordercolor=BORDER,
            # Explicit ink. Without it Plotly keeps the auto-contrast colour it
            # computed from the trace fill, which once rendered white on white.
            font=dict(color=INK, size=12, family=FONT_STACK),
        )
    )
    return fig


def render_mobile_chart(fig, chart_type='default'):
    import streamlit as st
    fig = apply_mobile_optimization(fig, chart_type)
    st.plotly_chart(fig, use_container_width=True, config=get_mobile_config())
```

Note: `donut`, `heatmap` and `gauge` entries are gone — the donut and gauge are
deleted in later tasks, and no caller used `heatmap` for an actual heatmap.

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_theme.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/mobile_plotly_config.py tests/test_theme.py
git commit -m "Re-tokenize the shared Plotly layer and drop its dead helpers"
```

---

### Task 3: `get_attrition_series`

**Files:**
- Modify: `app/dashboard_data.py`
- Test: `tests/test_dashboard_data.py` (append)

**Interfaces:**
- Produces: `build_attrition_rows(entrants: int, elims_by_week: Dict[int, int], weeks: List[int]) -> List[Dict]` (pure, testable) and `get_attrition_series(season: int) -> List[Dict]` (cached). Each row: `{"week": int, "entering": int, "eliminated": int, "remaining": int, "pct_out": float}`.

This is the shared spine: it feeds the KPI sparkline, the Elimination Tracker and the
Survivors context line. It replaces `chaos_meter`'s three-queries-per-week loop —
42 round trips for 2025, now 1.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_dashboard_data.py
from app.dashboard_data import build_attrition_rows


class TestBuildAttritionRows:
    def test_matches_the_real_2025_shape(self):
        elims = {1: 6, 2: 8, 3: 67, 4: 44, 5: 53, 6: 13, 7: 1,
                 8: 21, 9: 7, 10: 11, 11: 0, 12: 0, 13: 2, 14: 18}
        rows = build_attrition_rows(252, elims, list(range(1, 15)))
        assert rows[0]["entering"] == 252
        assert rows[0]["remaining"] == 246
        assert rows[2]["entering"] == 238   # week 3
        assert rows[5]["entering"] == 74    # week 6
        assert rows[-1]["remaining"] == 1   # the season really ended at one

    def test_entering_equals_previous_remaining(self):
        elims = {1: 5, 2: 3, 3: 0}
        rows = build_attrition_rows(20, elims, [1, 2, 3])
        for prev, cur in zip(rows, rows[1:]):
            assert cur["entering"] == prev["remaining"]

    def test_a_week_with_no_eliminations_is_flat(self):
        rows = build_attrition_rows(10, {1: 0}, [1])
        assert rows[0]["entering"] == rows[0]["remaining"] == 10
        assert rows[0]["pct_out"] == 0.0

    def test_missing_week_key_counts_as_zero(self):
        rows = build_attrition_rows(10, {}, [1, 2])
        assert [r["remaining"] for r in rows] == [10, 10]

    def test_pct_out_is_of_players_entering_that_week(self):
        rows = build_attrition_rows(200, {1: 50}, [1])
        assert rows[0]["pct_out"] == pytest.approx(25.0)

    def test_no_entrants_does_not_divide_by_zero(self):
        rows = build_attrition_rows(0, {}, [1])
        assert rows[0]["pct_out"] == 0.0

    def test_empty_weeks_gives_empty_series(self):
        assert build_attrition_rows(252, {}, []) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q -k Attrition`
Expected: FAIL — `ImportError: cannot import name 'build_attrition_rows'`

- [ ] **Step 3: Implement in `app/dashboard_data.py`**

```python
def build_attrition_rows(entrants, elims_by_week, weeks):
    """Turn {week: first-eliminations} into the field's week-by-week decline.

    Pure so the arithmetic is testable without a database. `entering` is the
    field at the start of the week; `remaining` is what survived it.
    """
    rows = []
    alive = entrants
    for week in sorted(weeks):
        out = elims_by_week.get(week, 0)
        entering = alive
        alive = entering - out
        rows.append({
            "week": week,
            "entering": entering,
            "eliminated": out,
            "remaining": alive,
            "pct_out": round(out / entering * 100, 1) if entering > 0 else 0.0,
        })
    return rows


@st.cache_data(ttl=60)
def get_attrition_series(season: int):
    """The field's week-by-week decline, in one query.

    Each player is attributed to the week of their FIRST losing pick, matching
    the graveyard. Replaces chaos_meter's three-queries-per-week loop.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        entrants = count_season_entrants(db, season)

        first_elim = db.query(
            Pick.player_id,
            func.min(Pick.week).label("week"),
        ).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == season,
            PickResult.survived == False,  # noqa: E712
        ).group_by(Pick.player_id).subquery()

        elim_rows = db.query(
            first_elim.c.week,
            func.count().label("n"),
        ).group_by(first_elim.c.week).all()
        elims = {week: n for week, n in elim_rows}

        week_rows = db.query(Pick.week).filter(
            Pick.season == season
        ).distinct().all()
        weeks = sorted(w[0] for w in week_rows)

        # Never project past the last week that kicked off - the sheet holds
        # picks for unplayed weeks.
        started = get_started_game_weeks(season)
        if started:
            weeks = [w for w in weeks if w <= max(started)]

        return build_attrition_rows(entrants, elims, weeks)
    finally:
        try:
            db.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: PASS

- [ ] **Step 5: Verify against the real 2025 data**

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/python -c "
from app.dashboard_data import get_attrition_series
for r in get_attrition_series(2025): print(r)"
```
Expected: week 1 entering 252, week 6 entering 74, final remaining 1.

- [ ] **Step 6: Commit**

```bash
git add app/dashboard_data.py tests/test_dashboard_data.py
git commit -m "Add cached get_attrition_series, replacing the per-week loop"
```

---

### Task 4: `get_doom_teams` and `get_graveyard`

**Files:**
- Modify: `app/dashboard_data.py`
- Test: `tests/test_dashboard_data.py` (append)

**Interfaces:**
- Produces: `rank_doom_teams(rows: List[Tuple[str, int, int]]) -> List[Dict]` (pure); `get_doom_teams(season: int) -> List[Dict]` with keys `team`, `eliminations`, `worst_week`; `get_graveyard(season: int) -> List[Dict]` with keys `player`, `week`, `team`, `opponent`, `location`, `margin`, `final_score`, `game_summary`

`get_doom_teams` uses **first-elimination** attribution (`MIN(week)` per player),
matching the graveyard. The old `team_of_doom.py` counted every losing pick. In 2025
these agree exactly (GB is 73 either way) because eliminated players stop filling the
sheet — the divergence is latent, not visible.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_dashboard_data.py
from app.dashboard_data import rank_doom_teams


class TestRankDoomTeams:
    def test_orders_by_eliminations_descending(self):
        out = rank_doom_teams([("LAC", 32, 5), ("GB", 73, 3), ("ATL", 28, 3)])
        assert [t["team"] for t in out] == ["GB", "LAC", "ATL"]

    def test_ties_break_alphabetically_for_a_stable_order(self):
        out = rank_doom_teams([("MIN", 3, 2), ("PIT", 3, 4), ("NE", 3, 1)])
        assert [t["team"] for t in out] == ["MIN", "NE", "PIT"]

    def test_carries_the_worst_week_through(self):
        out = rank_doom_teams([("GB", 73, 3)])
        assert out[0]["worst_week"] == 3

    def test_drops_null_team_rows(self):
        # A missed pick has team_abbr NULL. It eliminates players but it is not
        # a team, and 2025 has 233 such picks - they would top the ranking.
        out = rank_doom_teams([("GB", 73, 3), (None, 233, 5)])
        assert [t["team"] for t in out] == ["GB"]

    def test_empty_input_gives_empty_output(self):
        assert rank_doom_teams([]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q -k Doom`
Expected: FAIL — `ImportError: cannot import name 'rank_doom_teams'`

- [ ] **Step 3: Implement in `app/dashboard_data.py`**

```python
def _first_elimination_subquery(db, season):
    """Each player's first losing week. The graveyard's definition of 'eliminated'."""
    return db.query(
        Pick.player_id,
        func.min(Pick.week).label("week"),
    ).join(
        PickResult, Pick.pick_id == PickResult.pick_id
    ).filter(
        Pick.season == season,
        PickResult.survived == False,  # noqa: E712
    ).group_by(Pick.player_id).subquery()


def rank_doom_teams(rows):
    """Order (team, eliminations, worst_week) triples for display.

    Rows with a null team are dropped: a missed pick eliminates a player but is
    not a team, and in 2025 there are 233 of them - they would top the ranking
    and mean nothing.
    """
    cleaned = [r for r in rows if r[0]]
    cleaned.sort(key=lambda r: (-r[1], r[0]))
    return [
        {"team": team, "eliminations": n, "worst_week": worst}
        for team, n, worst in cleaned
    ]


@st.cache_data(ttl=60)
def get_doom_teams(season: int):
    """Teams ranked by players they eliminated, first-elimination attributed."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        first = _first_elimination_subquery(db, season)
        rows = db.query(
            Pick.team_abbr,
            func.count(func.distinct(Pick.player_id)).label("n"),
            func.min(Pick.week).label("worst_week"),
        ).join(
            first,
            (Pick.player_id == first.c.player_id) & (Pick.week == first.c.week),
        ).filter(
            Pick.season == season
        ).group_by(Pick.team_abbr).all()
        return rank_doom_teams([(t, n, w) for t, n, w in rows])
    finally:
        try:
            db.close()
        except Exception:
            pass


@st.cache_data(ttl=60)
def get_graveyard(season: int):
    """Eliminated players and the pick that did it, one row per player."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        first = _first_elimination_subquery(db, season)
        rows = db.query(
            Player.display_name, Pick.week, Pick.team_abbr,
            Game.home_team, Game.away_team, Game.home_score, Game.away_score,
        ).join(
            Pick, Player.player_id == Pick.player_id
        ).join(
            first,
            (Pick.player_id == first.c.player_id) & (Pick.week == first.c.week),
        ).outerjoin(
            Game,
            ((Game.home_team == Pick.team_abbr) | (Game.away_team == Pick.team_abbr))
            & (Game.week == Pick.week) & (Game.season == season),
        ).filter(
            Pick.season == season
        ).order_by(Pick.week, Player.display_name).all()

        out = []
        for name, week, team, home, away, hs, as_ in rows:
            if team is None:
                out.append({
                    "player": name, "week": week, "team": None,
                    "opponent": None, "location": "", "margin": None,
                    "final_score": None, "game_summary": "No pick submitted",
                })
                continue
            if home == team:
                opponent, location, ts, os_ = away, "vs", hs, as_
            else:
                opponent, location, ts, os_ = home, "at", as_, hs
            out.append({
                "player": name, "week": week, "team": team,
                "opponent": opponent, "location": location,
                "margin": (os_ - ts) if ts is not None and os_ is not None else None,
                "final_score": f"{ts}-{os_}" if ts is not None else None,
                "game_summary": f"{team} {location} {opponent}",
            })
        return out
    finally:
        try:
            db.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: PASS

- [ ] **Step 5: Verify attribution against 2025**

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/python -c "
from app.dashboard_data import get_doom_teams, get_graveyard
print(get_doom_teams(2025)[:6])
print('graveyard rows:', len(get_graveyard(2025)))"
```
Expected: GB 73 first, then LAC 32, ATL 28, ARI 24, LAR 23, TB 16. Graveyard 251 rows.

- [ ] **Step 6: Commit**

```bash
git add app/dashboard_data.py tests/test_dashboard_data.py
git commit -m "Add cached get_doom_teams and get_graveyard on first-elimination attribution"
```

---

### Task 5: `get_survivor_board` and the `get_player_data` week clamp

**Files:**
- Modify: `app/dashboard_data.py`
- Test: `tests/test_dashboard_data.py` (append)

**Interfaces:**
- Produces: `get_survivor_board(season: int) -> List[Dict]` with keys `player`, `picks`, `teams_used`, `latest_week`, `latest_team`; `get_player_data(player_name: str, season: int)` gains a week clamp

Collapses `survivors.py`'s `2N + 2` round trips to one joined query. The old code also
started from `Player` without narrowing through the season's picks, so it counted every
player who ever entered the pool — the exact trap CLAUDE.md warns about.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_dashboard_data.py
class TestPlayerDataWeekClamp:
    def test_clamp_drops_future_weeks(self):
        from app.dashboard_data import clamp_picks_to_week
        picks = [{"week": 1}, {"week": 2}, {"week": 3}]
        assert [p["week"] for p in clamp_picks_to_week(picks, 2)] == [1, 2]

    def test_clamp_keeps_everything_at_or_before_the_week(self):
        from app.dashboard_data import clamp_picks_to_week
        picks = [{"week": 1}, {"week": 2}]
        assert len(clamp_picks_to_week(picks, 2)) == 2

    def test_clamp_to_none_is_a_no_op(self):
        from app.dashboard_data import clamp_picks_to_week
        picks = [{"week": 9}]
        assert clamp_picks_to_week(picks, None) == picks
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q -k Clamp`
Expected: FAIL — `ImportError: cannot import name 'clamp_picks_to_week'`

- [ ] **Step 3: Implement in `app/dashboard_data.py`**

```python
def clamp_picks_to_week(picks, current_week):
    """Drop picks for weeks that have not kicked off.

    The sheet holds future weeks' picks from day one, so returning them
    publishes the field's upcoming picks - the leak the picks grid exists to
    prevent. `None` means no clamp is known and the caller gets everything.
    """
    if current_week is None:
        return picks
    return [p for p in picks if p["week"] <= current_week]


@st.cache_data(ttl=60)
def get_survivor_board(season: int):
    """Every still-alive entrant with their pick history, in one query."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        eliminated = db.query(Pick.player_id).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == season,
            PickResult.survived == False,  # noqa: E712
        ).distinct().subquery()

        started = get_started_game_weeks(season)
        max_week = max(started) if started else None

        q = db.query(
            Player.display_name, Pick.week, Pick.team_abbr,
        ).join(
            Pick, Player.player_id == Pick.player_id
        ).filter(
            Pick.season == season,
            ~Player.player_id.in_(select(eliminated.c.player_id)),
        )
        if max_week is not None:
            q = q.filter(Pick.week <= max_week)

        by_player = {}
        for name, week, team in q.order_by(Player.display_name, Pick.week).all():
            entry = by_player.setdefault(name, {
                "player": name, "picks": 0, "teams_used": [],
                "latest_week": 0, "latest_team": None,
            })
            entry["picks"] += 1
            if team:
                entry["teams_used"].append(team)
            if week >= entry["latest_week"]:
                entry["latest_week"], entry["latest_team"] = week, team
        return list(by_player.values())
    finally:
        try:
            db.close()
        except Exception:
            pass
```

Then in the existing `get_player_data`, after the `picks` list is built and before
the return, clamp it:

```python
        started = get_started_game_weeks(season)
        picks = clamp_picks_to_week(picks, max(started) if started else None)

        return {
            "player": player_name,
            "season": season,
            "picks": picks,
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS, count >= 60 plus the new tests

- [ ] **Step 5: Verify the leak is closed**

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -c "
from app.dashboard_data import get_player_data, get_started_game_weeks, search_players
names = search_players('', 2026)
d = get_player_data(names[0], 2026) if names else None
print('started weeks:', get_started_game_weeks(2026))
print('weeks returned:', sorted({p[\"week\"] for p in d[\"picks\"]}) if d else 'n/a')"
```
Expected: no week greater than the last started week.

- [ ] **Step 6: Commit**

```bash
git add app/dashboard_data.py tests/test_dashboard_data.py
git commit -m "Collapse the survivors N+1 and clamp get_player_data to started weeks"
```

---

### Task 6: `app/attrition.py`

**Files:**
- Create: `app/attrition.py`
- Test: `tests/test_attrition.py`

**Interfaces:**
- Consumes: `get_attrition_series` rows; `app.theme`
- Produces: `build_sparkline(rows) -> go.Figure`, `build_attrition_chart(rows, current_week=None) -> go.Figure`, `describe_worst_stretch(rows) -> str | None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_attrition.py
import pytest
from app.attrition import build_sparkline, build_attrition_chart, describe_worst_stretch

ROWS_2025 = [
    {"week": 1, "entering": 252, "eliminated": 6, "remaining": 246, "pct_out": 2.4},
    {"week": 2, "entering": 246, "eliminated": 8, "remaining": 238, "pct_out": 3.3},
    {"week": 3, "entering": 238, "eliminated": 67, "remaining": 171, "pct_out": 28.2},
    {"week": 4, "entering": 171, "eliminated": 44, "remaining": 127, "pct_out": 25.7},
    {"week": 5, "entering": 127, "eliminated": 53, "remaining": 74, "pct_out": 41.7},
]


class TestSparkline:
    def test_plots_one_point_per_week(self):
        fig = build_sparkline(ROWS_2025)
        assert len(fig.data[0].x) == len(ROWS_2025)

    def test_is_short_enough_to_sit_inside_a_kpi_card(self):
        assert build_sparkline(ROWS_2025).layout.height <= 60

    def test_hides_both_axes(self):
        fig = build_sparkline(ROWS_2025)
        assert fig.layout.xaxis.visible is False
        assert fig.layout.yaxis.visible is False

    def test_single_week_still_renders(self):
        fig = build_sparkline(ROWS_2025[:1])
        assert len(fig.data[0].x) == 1

    def test_empty_rows_gives_an_empty_figure_not_a_crash(self):
        assert build_sparkline([]).data == ()


class TestAttritionChart:
    def test_plots_remaining_not_eliminated(self):
        fig = build_attrition_chart(ROWS_2025)
        assert list(fig.data[0].y) == [246, 238, 171, 127, 74]

    def test_marks_the_current_week(self):
        fig = build_attrition_chart(ROWS_2025, current_week=3)
        assert len(fig.layout.shapes) >= 1

    def test_no_marker_when_current_week_is_none(self):
        assert build_attrition_chart(ROWS_2025).layout.shapes == ()

    def test_empty_rows_gives_an_empty_figure(self):
        assert build_attrition_chart([]).data == ()


class TestDescribeWorstStretch:
    def test_names_the_cliff(self):
        # Weeks 3-5 remove 164 of 252 - the story the donut could not tell
        assert "3" in describe_worst_stretch(ROWS_2025)

    def test_returns_none_when_nobody_has_been_eliminated(self):
        flat = [{"week": 1, "entering": 5, "eliminated": 0,
                 "remaining": 5, "pct_out": 0.0}]
        assert describe_worst_stretch(flat) is None

    def test_returns_none_for_empty_rows(self):
        assert describe_worst_stretch([]) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_attrition.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.attrition'`

- [ ] **Step 3: Write `app/attrition.py`**

```python
"""
The field's decline, week by week.

Replaces the remaining-players donut. A donut shows a two-part ratio; 2025
ended at 1 survivor of 252, which as a ring is a solid band and as a curve is
a cliff in weeks 3-5 followed by a plateau in 11-13.
"""

import plotly.graph_objects as go

from app.theme import ACCENT, DANGER, INK, INK_MUTED, BORDER, FONT_STACK


def build_sparkline(rows):
    """A tiny remaining-players trace for the KPI card. No axes, no labels."""
    fig = go.Figure()
    if not rows:
        return fig

    fig.add_trace(go.Scatter(
        x=[r["week"] for r in rows],
        y=[r["remaining"] for r in rows],
        mode="lines",
        line=dict(color=ACCENT, width=2, shape="spline", smoothing=0.5),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.14)",
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=44,
        margin=dict(l=0, r=0, t=2, b=2),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, rangemode="tozero"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def build_attrition_chart(rows, current_week=None):
    """The full labelled curve, for the Elimination Tracker."""
    fig = go.Figure()
    if not rows:
        return fig

    weeks = [r["week"] for r in rows]
    fig.add_trace(go.Scatter(
        x=weeks,
        y=[r["remaining"] for r in rows],
        mode="lines+markers",
        line=dict(color=ACCENT, width=3),
        marker=dict(size=7, color=ACCENT),
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.10)",
        customdata=[[r["eliminated"], r["pct_out"]] for r in rows],
        hovertemplate=(
            "Week %{x}<br>%{y} still alive<br>"
            "%{customdata[0]} out (%{customdata[1]}%)<extra></extra>"
        ),
    ))

    if current_week is not None and current_week in weeks:
        fig.add_shape(
            type="line", x0=current_week, x1=current_week, y0=0, y1=1,
            yref="paper", line=dict(color=DANGER, width=1, dash="dot"),
        )

    fig.update_layout(
        height=280,
        margin=dict(l=8, r=8, t=8, b=28),
        font=dict(family=FONT_STACK, size=12, color=INK),
        xaxis=dict(title=None, tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, dtick=1),
        yaxis=dict(title=None, tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, rangemode="tozero"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


def describe_worst_stretch(rows, span=3):
    """Name the bloodiest run of weeks, e.g. 'Weeks 3-5 took 164'.

    Returns None when nobody has been eliminated, so the caller can show its
    own empty state rather than a sentence about zero.
    """
    if not rows or not any(r["eliminated"] for r in rows):
        return None
    if len(rows) < span:
        worst, total = rows[0], sum(r["eliminated"] for r in rows)
        return f"Week {worst['week']} took {total}"

    best_i, best_total = 0, -1
    for i in range(len(rows) - span + 1):
        total = sum(r["eliminated"] for r in rows[i:i + span])
        if total > best_total:
            best_i, best_total = i, total
    first, last = rows[best_i]["week"], rows[best_i + span - 1]["week"]
    return f"Weeks {first}-{last} took {best_total}"
```

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_attrition.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/attrition.py tests/test_attrition.py
git commit -m "Add the attrition sparkline and curve, replacing the donut"
```

---

### Task 7: `app/meme_cards.py`

**Files:**
- Create: `app/meme_cards.py`
- Test: `tests/test_meme_cards.py`

**Interfaces:**
- Consumes: `get_meme_stats(season)` output — `{"dumbest_picks": [...], "big_balls_picks": [...]}`
- Produces: `dumbest_card_rows(picks) -> List[Dict]`, `big_balls_card_rows(picks) -> List[Dict]`, `render_meme_stats(meme_stats) -> None`

**Big Balls must degrade.** Every 2025 game has `point_spread = NULL`, so
`was_underdog` never fires and the panel is road wins with counts of 1. The rows lead
with matchup and week; badges are optional garnish.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_meme_cards.py
from app.meme_cards import dumbest_card_rows, big_balls_card_rows

DUMBEST = [
    {"week": 3, "team": "ATL", "opponent": "CAR", "margin": 30, "eliminated_count": 12},
    {"week": 1, "team": "MIA", "opponent": "IND", "margin": 25, "eliminated_count": 2},
]
BIG_BALLS = [
    {"week": 14, "team": "SEA", "opponent": "ATL", "road_win": True,
     "was_underdog": False, "point_spread": None, "favorite_team": None,
     "big_balls_count": 1},
]


class TestDumbestCardRows:
    def test_ranks_from_one(self):
        assert [r["rank"] for r in dumbest_card_rows(DUMBEST)] == [1, 2]

    def test_headline_is_the_margin(self):
        assert dumbest_card_rows(DUMBEST)[0]["headline"] == "30"

    def test_matchup_reads_as_a_matchup(self):
        assert dumbest_card_rows(DUMBEST)[0]["matchup"] == "ATL vs CAR"

    def test_victim_line_is_singular_for_one(self):
        rows = dumbest_card_rows([{**DUMBEST[0], "eliminated_count": 1}])
        assert rows[0]["detail"] == "1 player eliminated"

    def test_victim_line_is_plural_for_many(self):
        assert dumbest_card_rows(DUMBEST)[0]["detail"] == "12 players eliminated"

    def test_caps_at_five(self):
        assert len(dumbest_card_rows(DUMBEST * 9)) == 5

    def test_carries_no_emoji(self):
        row = dumbest_card_rows(DUMBEST)[0]
        joined = "".join(str(v) for v in row.values())
        assert all(ord(ch) < 0x2500 for ch in joined)

    def test_empty_gives_empty(self):
        assert dumbest_card_rows([]) == []


class TestBigBallsCardRows:
    def test_road_win_uses_at_not_vs(self):
        assert big_balls_card_rows(BIG_BALLS)[0]["matchup"] == "SEA at ATL"

    def test_road_badge_present(self):
        assert "ROAD" in big_balls_card_rows(BIG_BALLS)[0]["badges"]

    def test_no_underdog_badge_without_spread_data(self):
        # The whole 2025 season looks like this
        assert "UNDERDOG" not in big_balls_card_rows(BIG_BALLS)[0]["badges"]

    def test_underdog_badge_when_the_flag_is_set(self):
        rows = big_balls_card_rows([{**BIG_BALLS[0], "was_underdog": True}])
        assert "UNDERDOG" in rows[0]["badges"]

    def test_home_win_uses_vs(self):
        rows = big_balls_card_rows([{**BIG_BALLS[0], "road_win": False}])
        assert rows[0]["matchup"] == "SEA vs ATL"

    def test_headline_is_the_player_count(self):
        assert big_balls_card_rows(BIG_BALLS)[0]["headline"] == "1"

    def test_empty_gives_empty(self):
        assert big_balls_card_rows([]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_meme_cards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.meme_cards'`

- [ ] **Step 3: Write `app/meme_cards.py`**

```python
"""
Notable picks, as ranked cards.

These are the app's personality and they used to render as bare dataframes.
Row shaping is pure so the copy rules - pluralisation, badges, the no-emoji
rule - are testable without a Streamlit runtime.
"""

import html

import streamlit as st

from app.theme import ACCENT, BORDER, DANGER, INK, INK_MUTED, SURFACE_RAISED, WIN

MAX_CARDS = 5


def dumbest_card_rows(picks):
    """Shape the worst beatings for display, worst first."""
    rows = []
    for i, p in enumerate(picks[:MAX_CARDS], start=1):
        n = p["eliminated_count"]
        rows.append({
            "rank": i,
            "headline": str(p["margin"]),
            "headline_unit": "point loss",
            "matchup": f"{p['team']} vs {p['opponent']}",
            "week": f"Week {p['week']}",
            "detail": f"{n} player{'' if n == 1 else 's'} eliminated",
            "badges": [],
        })
    return rows


def big_balls_card_rows(picks):
    """Shape the risky wins.

    Leads with matchup and week rather than the underdog framing: 2025 has no
    spread data at all, so `was_underdog` never fires and a design that led
    with it would look broken on the whole season.
    """
    rows = []
    for i, p in enumerate(picks[:MAX_CARDS], start=1):
        road = p["road_win"]
        badges = []
        if p.get("was_underdog"):
            badges.append("UNDERDOG")
        if road:
            badges.append("ROAD")
        n = p["big_balls_count"]
        rows.append({
            "rank": i,
            "headline": str(n),
            "headline_unit": f"player{'' if n == 1 else 's'} survived it",
            "matchup": f"{p['team']} {'at' if road else 'vs'} {p['opponent']}",
            "week": f"Week {p['week']}",
            "detail": "",
            "badges": badges,
        })
    return rows


def _badge_html(text, tone):
    return f'<span class="badge {tone}">{html.escape(text)}</span>'


def _render_hero(row, tone):
    badges = " ".join(_badge_html(b, tone) for b in row["badges"])
    st.markdown(
        f"""
        <div class="card" style="border-color:{BORDER};">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <div class="kpi-label">{html.escape(row['matchup'])}</div>
            <div class="kpi-label">{html.escape(row['week'])}</div>
          </div>
          <div style="font-size:3rem;font-weight:900;line-height:1;color:{INK};
                      font-variant-numeric:tabular-nums;margin:.2rem 0;">
            {html.escape(row['headline'])}
            <span style="font-size:.9rem;font-weight:600;color:{INK_MUTED};">
              {html.escape(row['headline_unit'])}</span>
          </div>
          <div class="kpi-sub">{html.escape(row['detail'])} {badges}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_row(row, tone):
    badges = " ".join(_badge_html(b, tone) for b in row["badges"])
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;gap:.6rem;
                    padding:.45rem 0;border-bottom:1px solid {BORDER};">
          <span style="color:{INK_MUTED};font-size:.78rem;width:1.4rem;">
            {row['rank']}</span>
          <span style="color:{INK};font-weight:600;flex:1;">
            {html.escape(row['matchup'])}</span>
          <span style="color:{INK_MUTED};font-size:.78rem;">
            {html.escape(row['week'])}</span>
          <span style="color:{INK};font-weight:700;
                       font-variant-numeric:tabular-nums;">
            {html.escape(row['headline'])}</span>
          {badges}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_panel(title, subtitle, rows, empty_message, tone):
    st.markdown(f'<div class="eyebrow">{html.escape(title)}</div>',
                unsafe_allow_html=True)
    st.caption(subtitle)
    if not rows:
        st.info(empty_message)
        return
    _render_hero(rows[0], tone)
    for row in rows[1:]:
        _render_row(row, tone)


def render_meme_stats(meme_stats):
    """Render both notable-picks panels."""
    st.markdown('<div class="eyebrow">Notable picks</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _render_panel(
            "Dumbest picks",
            "The worst beatings anyone walked into.",
            dumbest_card_rows(meme_stats.get("dumbest_picks", [])),
            "No eliminations yet. This ranks the worst beatings once picks "
            "start losing.",
            "danger",
        )
    with right:
        _render_panel(
            "Big balls",
            "Road wins and underdog wins that paid off.",
            big_balls_card_rows(meme_stats.get("big_balls_picks", [])),
            "No risky wins yet. Road wins and underdog wins land here once "
            "week 1 is final.",
            "win",
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_meme_cards.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/meme_cards.py tests/test_meme_cards.py
git commit -m "Replace the meme dataframes with ranked cards"
```

---

### Task 8: Rewrite the four widget modules as view code

**Files:**
- Rewrite: `app/team_of_doom.py`, `app/graveyard.py`, `app/survivors.py`, `app/chaos_meter.py`
- Test: `tests/test_widgets.py`

**Interfaces:**
- Consumes: `get_doom_teams`, `get_graveyard`, `get_survivor_board`, `get_attrition_series`; `app.theme.contrast_fill`; `app.attrition`
- Produces: `render_team_of_doom_widget(season)`, `render_graveyard_widget(season)`, `render_survivors_widget(season)`, `render_chaos_meter_widget(season)` — **all lose the `db` parameter**

Deletes, all with zero call sites: `render_memorial_wall`, `render_graveyard_timeline`,
`render_doom_details`, `render_survivor_timeline`, `get_eliminated_count`,
`render_chaos_explanation`, `render_weekly_chaos_summary`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_widgets.py
import inspect

import pytest

from app import chaos_meter, graveyard, survivors, team_of_doom
from app.team_of_doom import build_doom_figure

MODULES = [team_of_doom, graveyard, survivors, chaos_meter]


class TestNoDatabaseAccessInViews:
    @pytest.mark.parametrize("module", MODULES)
    def test_module_never_opens_a_session(self, module):
        src = inspect.getsource(module)
        assert "SessionLocal" not in src
        assert "db.query" not in src

    @pytest.mark.parametrize("module,name", [
        (team_of_doom, "render_team_of_doom_widget"),
        (graveyard, "render_graveyard_widget"),
        (survivors, "render_survivors_widget"),
        (chaos_meter, "render_chaos_meter_widget"),
    ])
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
    ])
    def test_is_gone(self, module, name):
        assert not hasattr(module, name)


class TestNoEmoji:
    @pytest.mark.parametrize("module", MODULES)
    def test_source_carries_no_emoji(self, module):
        src = inspect.getsource(module)
        assert all(ord(ch) < 0x2500 for ch in src), module.__name__


class TestDoomFigure:
    ROWS = [
        {"team": "GB", "eliminations": 73, "worst_week": 3},
        {"team": "LAC", "eliminations": 32, "worst_week": 5},
    ]

    def test_one_bar_per_team(self):
        fig = build_doom_figure(self.ROWS, {"GB": "#203731", "LAC": "#0080C6"})
        assert len(fig.data[0].x) == 2

    def test_every_bar_clears_the_contrast_floor(self):
        from app.theme import contrast_ratio, SURFACE
        fig = build_doom_figure(self.ROWS, {"GB": "#203731", "LAC": "#0080C6"})
        for color in fig.data[0].marker.color:
            assert contrast_ratio(color, SURFACE) >= 3.0

    def test_unknown_team_gets_a_fallback_not_a_crash(self):
        fig = build_doom_figure([{"team": "ZZZ", "eliminations": 1,
                                  "worst_week": 1}], {})
        assert len(fig.data[0].x) == 1

    def test_empty_rows_gives_an_empty_figure(self):
        assert build_doom_figure([], {}).data == ()
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_widgets.py -q`
Expected: FAIL — modules still take `db`, dead functions still present

- [ ] **Step 3: Rewrite `app/team_of_doom.py`**

```python
"""
Teams ranked by how many entrants they eliminated.

Bars carry the team's own colour passed through contrast_fill, because a bar
floats on the surface with no border - unlike a grid cell, its legibility is
entirely fill-vs-surface contrast, and 22 of 32 team colours fail on the dark
surface untreated.
"""

import plotly.graph_objects as go
import streamlit as st

from app.dashboard_data import get_doom_teams, load_team_data
from app.mobile_plotly_config import get_mobile_config
from app.theme import BORDER, FONT_STACK, INK, INK_MUTED, SURFACE, contrast_fill

TOP_N = 10
FALLBACK = "#64748B"


def build_doom_figure(rows, team_colors):
    """Horizontal ranked bars, each in its team's contrast-corrected colour."""
    fig = go.Figure()
    if not rows:
        return fig

    rows = list(reversed(rows[:TOP_N]))  # plotly draws bottom-up
    fills = [
        contrast_fill(team_colors.get(r["team"], FALLBACK), SURFACE)
        for r in rows
    ]
    fig.add_trace(go.Bar(
        x=[r["eliminations"] for r in rows],
        y=[r["team"] for r in rows],
        orientation="h",
        marker=dict(color=fills, line=dict(width=0)),
        text=[str(r["eliminations"]) for r in rows],
        textposition="outside",
        textfont=dict(color=INK, size=12, family=FONT_STACK),
        hovertemplate="%{y}: %{x} eliminated<extra></extra>",
    ))
    fig.update_layout(
        height=max(220, len(rows) * 30 + 60),
        margin=dict(l=8, r=36, t=8, b=24),
        font=dict(family=FONT_STACK, size=12, color=INK),
        xaxis=dict(visible=False),
        yaxis=dict(tickfont=dict(color=INK_MUTED, size=12), gridcolor=BORDER),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.3,
    )
    return fig


@st.fragment
def render_team_of_doom_widget(season):
    """Render the Team of Doom ranking."""
    st.markdown('<div class="eyebrow">Team of doom</div>', unsafe_allow_html=True)
    st.caption("Teams that ended the most entrants' seasons.")

    rows = get_doom_teams(season)
    if not rows:
        st.info(
            "Nobody has been eliminated yet. This fills in when a picked team "
            "loses a completed week."
        )
        return

    colors = {t: d.get("color", FALLBACK)
              for t, d in load_team_data()["teams"].items()}
    st.plotly_chart(build_doom_figure(rows, colors),
                    use_container_width=True, config=get_mobile_config())

    top = rows[0]
    st.caption(
        f"{top['team']} ended {top['eliminations']} runs - "
        f"more than the next {min(3, len(rows) - 1)} teams combined."
        if len(rows) > 3 and top["eliminations"] > sum(
            r["eliminations"] for r in rows[1:4])
        else f"{top['team']} ended {top['eliminations']} runs."
    )
```

- [ ] **Step 4: Rewrite `app/graveyard.py`**

```python
"""
Eliminated entrants and the pick that ended them.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.dashboard_data import get_graveyard
from app.mobile_plotly_config import get_mobile_config
from app.theme import BORDER, DANGER, FONT_STACK, INK, INK_MUTED

ALL_WEEKS = "All weeks"


def build_elimination_bars(rows):
    """Eliminations per week. One colour - height already encodes magnitude."""
    fig = go.Figure()
    if not rows:
        return fig

    by_week = {}
    for r in rows:
        by_week[r["week"]] = by_week.get(r["week"], 0) + 1
    weeks = sorted(by_week)

    fig.add_trace(go.Bar(
        x=weeks,
        y=[by_week[w] for w in weeks],
        marker=dict(color=DANGER, line=dict(width=0)),
        text=[by_week[w] for w in weeks],
        textposition="outside",
        textfont=dict(color=INK_MUTED, size=11, family=FONT_STACK),
        hovertemplate="Week %{x}: %{y} eliminated<extra></extra>",
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=8, r=8, t=16, b=24),
        font=dict(family=FONT_STACK, size=12, color=INK),
        xaxis=dict(tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, dtick=1),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.35,
    )
    return fig


@st.fragment
def render_graveyard_widget(season):
    """Render the graveyard board."""
    st.markdown('<div class="eyebrow">Graveyard</div>', unsafe_allow_html=True)
    st.caption("Everyone who is out, and the pick that did it.")

    rows = get_graveyard(season)
    if not rows:
        st.info(
            "The graveyard is empty. The first headstone lands when a picked "
            "team loses a completed week."
        )
        return

    st.plotly_chart(build_elimination_bars(rows),
                    use_container_width=True, config=get_mobile_config())

    weeks = sorted({r["week"] for r in rows})
    choice = st.selectbox(
        "Elimination week", [ALL_WEEKS] + [f"Week {w}" for w in weeks],
        key="graveyard_week",
    )
    shown = rows if choice == ALL_WEEKS else [
        r for r in rows if r["week"] == int(choice.split()[1])
    ]

    st.dataframe(
        pd.DataFrame([{
            "Player": r["player"],
            "Week": r["week"],
            "Pick": r["team"] or "No pick",
            "Game": r["game_summary"],
            "Score": r["final_score"] or "-",
            "Lost by": r["margin"] if r["margin"] is not None else "-",
        } for r in shown]),
        use_container_width=True, hide_index=True,
    )
```

- [ ] **Step 5: Rewrite `app/survivors.py`**

```python
"""
Entrants still alive.
"""

import pandas as pd
import streamlit as st

from app.dashboard_data import get_attrition_series, get_survivor_board
from app.theme import INK_MUTED


def render_survivors_widget(season):
    """Render the survivors board."""
    st.markdown('<div class="eyebrow">Survivors</div>', unsafe_allow_html=True)
    st.caption("Still alive, and what they have spent.")

    rows = get_survivor_board(season)
    if not rows:
        st.info(
            "No survivors left. Every entrant has been eliminated - the pool "
            "is over."
        )
        return

    series = get_attrition_series(season)
    left, right = st.columns(2)
    with left:
        st.markdown(
            f'<div class="kpi-label">Still alive</div>'
            f'<div class="kpi-value">{len(rows)}</div>',
            unsafe_allow_html=True,
        )
    with right:
        started = series[0]["entering"] if series else len(rows)
        st.markdown(
            f'<div class="kpi-label">Started</div>'
            f'<div class="kpi-value">{started}</div>',
            unsafe_allow_html=True,
        )

    st.dataframe(
        pd.DataFrame([{
            "Player": r["player"],
            "Picks": r["picks"],
            "Latest": (f"Week {r['latest_week']}: {r['latest_team']}"
                       if r["latest_week"] else "No picks yet"),
            "Teams used": ", ".join(r["teams_used"]) or "-",
        } for r in sorted(rows, key=lambda r: r["player"])]),
        use_container_width=True, hide_index=True,
    )
```

- [ ] **Step 6: Rewrite `app/chaos_meter.py`**

```python
"""
Elimination rate, week by week.

The gauge this replaces was the most dated object in the app. The curve is
built by app.attrition rather than a fifth chart idiom.
"""

import streamlit as st

from app.attrition import build_attrition_chart, describe_worst_stretch
from app.dashboard_data import get_attrition_series
from app.mobile_plotly_config import get_mobile_config


def render_chaos_meter_widget(season):
    """Render the elimination tracker."""
    st.markdown('<div class="eyebrow">Elimination tracker</div>',
                unsafe_allow_html=True)
    st.caption("How fast the field is collapsing.")

    series = get_attrition_series(season)
    if not series:
        st.info(
            "No completed weeks yet. Elimination rates appear once a week's "
            "games are final."
        )
        return

    latest = series[-1]
    c1, c2, c3 = st.columns(3)
    for col, label, value in (
        (c1, "Still alive", f"{latest['remaining']:,}"),
        (c2, f"Out in week {latest['week']}", f"{latest['eliminated']:,}"),
        (c3, "Week rate", f"{latest['pct_out']:.1f}%"),
    ):
        with col:
            st.markdown(
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>',
                unsafe_allow_html=True,
            )

    st.plotly_chart(
        build_attrition_chart(series, current_week=latest["week"]),
        use_container_width=True, config=get_mobile_config(),
    )

    worst = describe_worst_stretch(series)
    if worst:
        st.caption(f"Bloodiest stretch: {worst}.")
```

- [ ] **Step 7: Run to verify pass**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add app/team_of_doom.py app/graveyard.py app/survivors.py app/chaos_meter.py tests/test_widgets.py
git commit -m "Rewrite the four Pool Insights widgets as pure view code"
```

---

### Task 9: Wire `main.py`

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_widgets.py` (append)

**Interfaces:**
- Consumes: everything above
- Produces: no new public API

**Do not touch** `render_weekly_picks_chart` beyond leaving it as-is, and do not touch
the live-scores block. `APP_SURFACE` at line 62 becomes `SURFACE` imported from
`app.theme` — a one-line token swap that keeps the grid's history muting correct.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_widgets.py
class TestMainWiring:
    def test_donut_is_gone(self):
        src = open("app/main.py").read()
        assert "render_remaining_players_donut" not in src
        assert "go.Pie" not in src

    def test_no_inline_css_block_remains(self):
        src = open("app/main.py").read()
        assert "@import url" not in src
        assert "!important" not in src

    def test_surface_comes_from_theme(self):
        src = open("app/main.py").read()
        assert "APP_SURFACE" not in src
        assert "from app.theme import" in src

    def test_insights_tabs_open_no_sessions(self):
        src = open("app/main.py").read()
        # The live-scores block still opens one; the four tabs must not.
        assert src.count("SessionLocal()") <= 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_widgets.py -q -k MainWiring`
Expected: FAIL

- [ ] **Step 3: Apply the edits to `app/main.py`**

Replace the imports of the four widgets and the mobile config:

```python
from app.theme import GLOBAL_CSS, SURFACE
from app.attrition import build_sparkline, describe_worst_stretch
from app.meme_cards import render_meme_stats
from app.team_of_doom import render_team_of_doom_widget
from app.graveyard import render_graveyard_widget
from app.survivors import render_survivors_widget
from app.chaos_meter import render_chaos_meter_widget
from app.mobile_plotly_config import get_mobile_config
```

Replace `APP_SURFACE = "#F8FAFC"` with nothing and change the one call site inside
`render_weekly_picks_chart` from `background=APP_SURFACE` to `background=SURFACE`.
Delete `COUNT_LABEL`/`PERCENT_LABEL` only if unused elsewhere — they are not.

Replace the whole `st.markdown("""<style>...""", unsafe_allow_html=True)` block with:

```python
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
```

Replace the KPI row so "Players Remaining" carries the sparkline:

```python
    try:
        summary_preview = get_summary_data(SEASON)
        series = get_attrition_series(SEASON)

        st.markdown('<div class="eyebrow">Key stats</div>', unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)

        remaining = summary_preview.get("entrants_remaining", 0)
        total = summary_preview.get("entrants_total", 0)

        with k1:
            st.markdown(
                f'<div class="kpi-label">Players remaining</div>'
                f'<div class="kpi-value">{remaining:,}</div>',
                unsafe_allow_html=True,
            )
            if series:
                st.plotly_chart(build_sparkline(series),
                                use_container_width=True,
                                config=get_mobile_config())
                worst = describe_worst_stretch(series)
                st.markdown(
                    f'<div class="kpi-sub">of {total:,} entered'
                    + (f' - {worst}' if worst else '') + '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="kpi-sub">of {total:,} entered - the curve '
                    f'starts once week 1 is final</div>',
                    unsafe_allow_html=True,
                )
        with k2:
            st.markdown(
                f'<div class="kpi-label">Eliminated</div>'
                f'<div class="kpi-value">{total - remaining:,}</div>'
                f'<div class="kpi-sub">out of the running</div>',
                unsafe_allow_html=True,
            )
        with k3:
            weeks_played = get_completed_week_count(SEASON)
            st.markdown(
                f'<div class="kpi-label">Weeks completed</div>'
                f'<div class="kpi-value">{weeks_played:,}</div>'
                f'<div class="kpi-sub">survival rounds</div>',
                unsafe_allow_html=True,
            )
    except Exception:
        logging.exception("KPI row failed to render")
```

Add `get_attrition_series` to the `app.dashboard_data` import list.

Replace the two-column donut/search block with a full-width search:

```python
    render_player_search()
```

and delete `render_remaining_players_donut` entirely.

Replace the four tab bodies — the `SessionLocal()` wrappers go with them:

```python
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Team of Doom", "Survivors", "Graveyard", "Elimination Tracker"]
    )
    with tab1:
        render_team_of_doom_widget(SEASON)
    with tab2:
        render_survivors_widget(SEASON)
    with tab3:
        render_graveyard_widget(SEASON)
    with tab4:
        render_chaos_meter_widget(SEASON)
```

Delete the `render_meme_stats` definition from `main.py` (it now lives in
`meme_cards.py`) and strip emoji from the remaining headings and captions in
`render_player_search` and `render_footer`.

- [ ] **Step 4: Run the full suite**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_widgets.py
git commit -m "Wire the dashboard to the new theme, KPI sparkline and view widgets"
```

---

### Task 10: Verify against both seasons and a phone viewport

**Files:** none modified unless a defect is found

- [ ] **Step 1: Headless smoke test on both seasons**

```python
# scratch check - do not commit
from streamlit.testing.v1 import AppTest
for season in ("2025", "2026"):
    import os; os.environ["NFL_SEASON"] = season
    at = AppTest.from_file("app/main.py", default_timeout=90).run()
    assert not at.exception, (season, at.exception)
    print(season, "ok")
```

Run with `DATABASE_URL` set to the public URL. Expected: both clean.

- [ ] **Step 2: Confirm the empty states actually appear on 2026**

Run the app with `NFL_SEASON=2026`. Every Pool Insights tab and both meme panels must
show their own sentence naming the precondition, not a blank panel.

- [ ] **Step 3: Confirm 2025 renders the real story**

Run with `NFL_SEASON=2025`. Check: KPI reads 1 remaining of 252; the sparkline shows
the week 3-5 cliff; Team of Doom leads GB 73; the graveyard table has 251 rows.

- [ ] **Step 4: Phone-width check at 390px**

Open at 390px wide. Confirm no horizontal scroll, the KPI numerals do not clip, the
doom bar labels stay inside the plot, and the meme hero card wraps rather than
overflowing.

- [ ] **Step 5: Confirm no emoji survive in the touched files**

```bash
grep -nP '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' app/main.py app/graveyard.py \
  app/survivors.py app/team_of_doom.py app/chaos_meter.py app/meme_cards.py \
  app/attrition.py app/theme.py || echo "clean"
```
Expected: `clean`

- [ ] **Step 6: Commit any fixes**

```bash
git add -A && git commit -m "Fix defects found in cross-season and mobile verification"
```

---

## Self-Review

**Spec coverage:** §1 foundation → Task 1. §2 data layer → Tasks 3-5. §3 charts →
Tasks 6, 8. §4 KPI and meme cards → Tasks 6, 7, 9. §5 performance/rules → Tasks 5, 8
(`st.fragment`), 9. §6 testing → every task. §7 empty states → Tasks 7, 8, 9. Emoji
rule → Tasks 7, 8, 9, verified in Task 10. Blast radius → Task 2 (mine); the three
`picks_grid.py` items are Session B's and correctly absent.

**Placeholders:** none. Every code step carries real code.

**Type consistency:** `contrast_fill(color, background, target)` used identically in
Tasks 1, 2, 8. Attrition row keys (`week`, `entering`, `eliminated`, `remaining`,
`pct_out`) identical in Tasks 3, 6, 8, 9. Doom row keys (`team`, `eliminations`,
`worst_week`) identical in Tasks 4, 8. `render_*(season)` signature consistent in
Tasks 8 and 9.

**Known gap, deliberate:** Task 9 leaves the live-scores `SessionLocal()` block in
place. It is Session B's region.
