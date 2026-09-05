"""
Teams ranked by how many entrants they eliminated.

Bars carry the team's own colour passed through contrast_fill. A bar floats on
the surface with no border, so - unlike a grid cell, which carries a hairline
and contrast-derived ink - its legibility is entirely fill-vs-surface contrast,
and 22 of 32 team colours fail that on the dark surface untreated.
"""

import plotly.graph_objects as go
import streamlit as st

from app.dashboard_data import get_doom_teams, load_team_data
from app.mobile_plotly_config import get_mobile_config
from app.theme import BORDER, FONT_STACK, INK, INK_MUTED, SURFACE, contrast_fill

TOP_N = 10
FALLBACK_COLOR = "#64748B"


def build_doom_figure(rows, team_colors):
    """Horizontal ranked bars, each in its team's contrast-corrected colour."""
    fig = go.Figure()
    if not rows:
        return fig

    # plotly draws horizontal bars bottom-up, so reverse to put rank 1 on top
    shown = list(reversed(rows[:TOP_N]))
    fills = [
        contrast_fill(team_colors.get(row["team"], FALLBACK_COLOR), SURFACE)
        for row in shown
    ]

    fig.add_trace(go.Bar(
        x=[row["eliminations"] for row in shown],
        y=[row["team"] for row in shown],
        orientation="h",
        marker=dict(color=fills, line=dict(width=0)),
        text=[str(row["eliminations"]) for row in shown],
        textposition="outside",
        textfont=dict(color=INK, size=12, family=FONT_STACK),
        cliponaxis=False,
        hovertemplate="%{y}: %{x} eliminated<extra></extra>",
    ))
    fig.update_layout(
        height=max(220, len(shown) * 30 + 60),
        margin=dict(l=8, r=40, t=8, b=24),
        font=dict(family=FONT_STACK, size=12, color=INK),
        xaxis=dict(visible=False),
        yaxis=dict(tickfont=dict(color=INK_MUTED, size=12),
                   gridcolor=BORDER, showgrid=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.3,
    )
    return fig


def _lead_caption(rows):
    """Say something true about the leader, not a generic restatement."""
    leader = rows[0]
    chasers = rows[1:4]
    if len(chasers) == 3 and leader["eliminations"] > sum(
            r["eliminations"] for r in chasers):
        return (f"{leader['team']} ended {leader['eliminations']} runs - more "
                f"than the next three teams combined.")
    return f"{leader['team']} ended {leader['eliminations']} runs."


@st.fragment
def render_team_of_doom_widget(season):
    """Render the Team of Doom ranking."""
    st.markdown('<div class="eyebrow">Team of doom</div>', unsafe_allow_html=True)
    st.caption("Teams that ended the most entrants' seasons.")

    rows = get_doom_teams(season)
    if not rows:
        st.info("Nobody has been eliminated yet. This fills in when a picked "
                "team loses a completed week.")
        return

    colors = {team: data.get("color", FALLBACK_COLOR)
              for team, data in load_team_data()["teams"].items()}
    st.plotly_chart(build_doom_figure(rows, colors),
                    use_container_width=True, config=get_mobile_config())
    st.caption(_lead_caption(rows))
