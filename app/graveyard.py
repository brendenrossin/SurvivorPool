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
    """Eliminations per week.

    One colour throughout: bar height already encodes magnitude, and a
    sequential fill on top of it would encode the same thing twice.
    """
    fig = go.Figure()
    if not rows:
        return fig

    per_week = {}
    for row in rows:
        per_week[row["week"]] = per_week.get(row["week"], 0) + 1
    weeks = sorted(per_week)

    fig.add_trace(go.Bar(
        x=weeks,
        y=[per_week[w] for w in weeks],
        marker=dict(color=DANGER, line=dict(width=0)),
        text=[per_week[w] for w in weeks],
        textposition="outside",
        textfont=dict(color=INK_MUTED, size=11, family=FONT_STACK),
        cliponaxis=False,
        hovertemplate="Week %{x}: %{y} eliminated<extra></extra>",
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=8, r=8, t=18, b=24),
        font=dict(family=FONT_STACK, size=12, color=INK),
        xaxis=dict(tickfont=dict(color=INK_MUTED, size=11),
                   gridcolor=BORDER, showgrid=False, dtick=1),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        bargap=0.35,
    )
    return fig


def _table_rows(rows):
    return pd.DataFrame([{
        "Player": row["player"],
        "Week": row["week"],
        "Pick": row["team"] or "No pick",
        "Game": row["game_summary"],
        "Score": row["final_score"] or "-",
        "Lost by": row["margin"] if row["margin"] is not None else "-",
    } for row in rows])


@st.fragment
def render_graveyard_widget(season):
    """Render the graveyard board."""
    st.markdown('<div class="eyebrow">Graveyard</div>', unsafe_allow_html=True)
    st.caption("Everyone who is out, and the pick that did it.")

    rows = get_graveyard(season)
    if not rows:
        st.info("The graveyard is empty. The first headstone lands when a "
                "picked team loses a completed week.")
        return

    st.plotly_chart(build_elimination_bars(rows),
                    use_container_width=True, config=get_mobile_config())

    weeks = sorted({row["week"] for row in rows})
    choice = st.selectbox(
        "Elimination week",
        [ALL_WEEKS] + [f"Week {w}" for w in weeks],
        key="graveyard_week",
    )
    shown = rows if choice == ALL_WEEKS else [
        row for row in rows if row["week"] == int(choice.split()[1])
    ]

    st.dataframe(_table_rows(shown), use_container_width=True, hide_index=True)
