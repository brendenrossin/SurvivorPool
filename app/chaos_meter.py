"""
Elimination rate, week by week.

The gauge this replaces was the most dated object in the app. The curve comes
from app.attrition rather than a fifth chart idiom.
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
        st.info("No completed weeks yet. Elimination rates appear once a "
                "week's games are final.")
        return

    latest = series[-1]
    columns = st.columns(3)
    stats = (
        ("Still alive", f"{latest['remaining']:,}"),
        (f"Out in week {latest['week']}", f"{latest['eliminated']:,}"),
        ("Week rate", f"{latest['pct_out']:.1f}%"),
    )
    for column, (label, value) in zip(columns, stats):
        with column:
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
