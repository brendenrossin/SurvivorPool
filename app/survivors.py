"""
Entrants still alive.
"""

import pandas as pd
import streamlit as st

from app.dashboard_data import get_attrition_series, get_survivor_board


def _table_rows(rows):
    return pd.DataFrame([{
        "Player": row["player"],
        "Picks": row["picks"],
        "Latest": (f"Week {row['latest_week']}: {row['latest_team']}"
                   if row["latest_week"] else "No picks yet"),
        "Teams used": ", ".join(row["teams_used"]) or "-",
    } for row in sorted(rows, key=lambda r: r["player"])])


def render_survivors_widget(season):
    """Render the survivors board."""
    st.markdown('<div class="eyebrow">Survivors</div>', unsafe_allow_html=True)
    st.caption("Still alive, and what they have spent.")

    rows = get_survivor_board(season)
    if not rows:
        st.info("No survivors left. Every entrant has been eliminated and the "
                "pool is over.")
        return

    series = get_attrition_series(season)
    started = series[0]["entering"] if series else len(rows)

    left, right = st.columns(2)
    with left:
        st.markdown(
            '<div class="kpi-label">Still alive</div>'
            f'<div class="kpi-value">{len(rows):,}</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            '<div class="kpi-label">Started</div>'
            f'<div class="kpi-value">{started:,}</div>',
            unsafe_allow_html=True,
        )

    st.dataframe(_table_rows(rows), use_container_width=True, hide_index=True)
