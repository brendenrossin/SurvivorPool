"""
The field's decline, week by week.

Replaces the remaining-players donut. A donut shows a two-part ratio; 2025
ended at 1 survivor of 252, which as a ring is a solid band. As a curve it is
a cliff in weeks 3-5 followed by a plateau in 11-13, which is the story worth
telling.
"""

import plotly.graph_objects as go

from app.mobile_plotly_config import lock_zoom
from app.theme import ACCENT, BORDER, DANGER, FONT_STACK, INK, INK_MUTED

# Accent at low alpha. Kept as a literal rather than a token because it is a
# fill wash derived from ACCENT, not an independent colour decision.
_WASH = "rgba(245,158,11,0.14)"
_WASH_FAINT = "rgba(245,158,11,0.10)"

WORST_STRETCH_SPAN = 3

# The curve opens on the field before a single game was played. That is not a
# week - there is no week 0 - so it is drawn one step before the first plotted
# week and labelled rather than numbered.
ANCHOR_LABEL = "Start"

MARKER_PX = 7
# A size smaller: the anchor is where the field started, not a week anyone
# survived. The relationship is the point, so it is derived, not repeated.
ANCHOR_MARKER_PX = MARKER_PX - 1


def _anchor_x(rows):
    """Where the opening point sits on the week axis.

    One step before the first *plotted* week, not a hard 0. The series holds
    only weeks that have kicked off, so when the pool's first played week is
    not week 1 a fixed 0 stretches the opening segment across weeks that never
    happened and implies the field held flat through them.
    """
    return rows[0]["week"] - 1


def _series_xy(rows):
    """x and y for the curve, including the opening anchor.

    The anchor is `rows[0]["entering"]`: the field at the start of the first
    played week, which - because `build_attrition_rows` sets `entering` before
    its first subtraction - is always the number everyone entered with, whether
    or not week 1 is in the series.

    Two things go wrong without it. A season one week old is a single point, and
    `mode="lines"` draws a one-point line as nothing at all - the KPI sparkline
    rendered an empty 44px box for the whole of week 1, which is what surfaced
    this. And the first and largest drop of the season, 300 to 179 in 2026,
    never appears: the curve starts at the survivors and the field it came from
    is only ever a caption.
    """
    if not rows:
        return [], []
    xs = [_anchor_x(rows)] + [r["week"] for r in rows]
    ys = [rows[0]["entering"]] + [r["remaining"] for r in rows]
    return xs, ys


def _series_hover(rows):
    """Hover text per point, anchor first. Only the full chart uses it - the
    sparkline sets hoverinfo="skip", so it never builds these strings."""
    if not rows:
        return []
    return [f"{ANCHOR_LABEL}<br>{rows[0]['entering']:,} entered"] + [
        f"Week {r['week']}<br>{r['remaining']:,} still alive<br>"
        f"{r['eliminated']:,} out ({r['pct_out']}%)"
        for r in rows
    ]


def build_sparkline(rows):
    """A tiny remaining-players trace for the KPI card. No axes, no labels."""
    fig = go.Figure()
    if not rows:
        return fig

    xs, ys = _series_xy(rows)
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="lines",
        line=dict(color=ACCENT, width=2, shape="spline", smoothing=0.5),
        fill="tozeroy",
        fillcolor=_WASH,
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
    return lock_zoom(fig)


def build_attrition_chart(rows, current_week=None):
    """The full labelled curve, for the elimination tracker."""
    fig = go.Figure()
    if not rows:
        return fig

    weeks = [r["week"] for r in rows]
    anchor_x = _anchor_x(rows)
    xs, ys = _series_xy(rows)
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="lines+markers",
        line=dict(color=ACCENT, width=3),
        marker=dict(
            size=[ANCHOR_MARKER_PX] + [MARKER_PX] * len(rows),
            color=[INK_MUTED] + [ACCENT] * len(rows),
        ),
        fill="tozeroy",
        fillcolor=_WASH_FAINT,
        hovertext=_series_hover(rows),
        hovertemplate="%{hovertext}<extra></extra>",
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
        # Explicit ticks rather than dtick=1, so the opening point reads
        # "Start" instead of naming a week that does not exist. Week labels stay
        # bare numbers: tickmode="array" disables Plotly's auto-thinning, so a
        # full 18-week season draws 19 labels and this is a 280px chart on a
        # mobile-first dashboard. "Start" already disambiguates the axis.
        xaxis=dict(title=None, tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, tickmode="array",
                   tickvals=[anchor_x] + weeks,
                   ticktext=[ANCHOR_LABEL] + [str(w) for w in weeks]),
        yaxis=dict(title=None, tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, rangemode="tozero"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return lock_zoom(fig)


def describe_worst_stretch(rows, span=WORST_STRETCH_SPAN):
    """Name the bloodiest run of weeks, e.g. "Weeks 3-5 took 164".

    Returns None when nobody has been eliminated, so the caller shows its own
    empty state rather than a sentence about zero.
    """
    if not rows or not any(r["eliminated"] for r in rows):
        return None

    if len(rows) < span:
        total = sum(r["eliminated"] for r in rows)
        first, last = rows[0]["week"], rows[-1]["week"]
        if first == last:
            return f"Week {first} took {total}"
        return f"Weeks {first}-{last} took {total}"

    best_index, best_total = 0, -1
    for i in range(len(rows) - span + 1):
        total = sum(r["eliminated"] for r in rows[i:i + span])
        if total > best_total:
            best_index, best_total = i, total

    first = rows[best_index]["week"]
    last = rows[best_index + span - 1]["week"]
    return f"Weeks {first}-{last} took {best_total}"
