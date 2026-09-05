"""
The field's decline, week by week.

Replaces the remaining-players donut. A donut shows a two-part ratio; 2025
ended at 1 survivor of 252, which as a ring is a solid band. As a curve it is
a cliff in weeks 3-5 followed by a plateau in 11-13, which is the story worth
telling.
"""

import plotly.graph_objects as go

from app.theme import ACCENT, BORDER, DANGER, FONT_STACK, INK, INK_MUTED

# Accent at low alpha. Kept as a literal rather than a token because it is a
# fill wash derived from ACCENT, not an independent colour decision.
_WASH = "rgba(245,158,11,0.14)"
_WASH_FAINT = "rgba(245,158,11,0.10)"

WORST_STRETCH_SPAN = 3


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
    return fig


def build_attrition_chart(rows, current_week=None):
    """The full labelled curve, for the elimination tracker."""
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
        fillcolor=_WASH_FAINT,
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
