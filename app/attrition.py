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

# The curve opens on the field before a single game was played. It is not a
# week - there is no week 0 - so it is drawn at x=0 and labelled.
ANCHOR_X = 0
ANCHOR_LABEL = "Start"


def _series_points(rows):
    """x, y and hover text for the curve, including the pre-week-1 anchor.

    The anchor is `rows[0]["entering"]`: the field at the start of the first
    played week, which is the number everyone entered with. Two things go wrong
    without it. A season one week old is a single point, and `mode="lines"`
    draws a one-point line as nothing at all - the KPI sparkline rendered an
    empty 44px box for the whole of week 1. And the first and largest drop of
    the season, 300 to 179 in 2026, never appears: the curve starts at the
    survivors and the field it came from is only ever a caption.

    Returns parallel lists so both figures share one definition of the curve.
    """
    entered = rows[0]["entering"]
    xs = [ANCHOR_X] + [r["week"] for r in rows]
    ys = [entered] + [r["remaining"] for r in rows]
    hover = [f"{ANCHOR_LABEL}<br>{entered:,} entered"] + [
        f"Week {r['week']}<br>{r['remaining']:,} still alive<br>"
        f"{r['eliminated']:,} out ({r['pct_out']}%)"
        for r in rows
    ]
    return xs, ys, hover


def build_sparkline(rows):
    """A tiny remaining-players trace for the KPI card. No axes, no labels."""
    fig = go.Figure()
    if not rows:
        return fig

    xs, ys, _ = _series_points(rows)
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
    xs, ys, hover = _series_points(rows)
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="lines+markers",
        line=dict(color=ACCENT, width=3),
        # The anchor is muted and a size smaller than the played weeks: it is
        # where the field started, not a week anyone survived.
        marker=dict(
            size=[6] + [7] * len(rows),
            color=[INK_MUTED] + [ACCENT] * len(rows),
        ),
        fill="tozeroy",
        fillcolor=_WASH_FAINT,
        hovertext=hover,
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
        # Explicit ticks rather than dtick=1, so x=0 reads "Start" instead of
        # naming a week that does not exist.
        xaxis=dict(title=None, tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, tickmode="array",
                   tickvals=[ANCHOR_X] + weeks,
                   ticktext=[ANCHOR_LABEL] + [f"W{w}" for w in weeks]),
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
