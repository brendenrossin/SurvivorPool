"""
Shared Plotly configuration.

Every layout value resolves through app.theme, so a surface change reaches
every chart routed through render_mobile_chart.

The picks grid deliberately does NOT route through here - it calls
st.plotly_chart directly, because CHART_CONFIGS would clobber its computed
height and its axis config. It therefore needs its own theming pass, which
belongs to whoever owns that module.
"""

import copy

from app.theme import BORDER, FONT_STACK, INK, INK_MUTED, SURFACE_RAISED

# Touch interactions only. Shared with the picks grid, which takes this config
# even though it skips the layout defaults above it.
MOBILE_CONFIG = {
    'displayModeBar': False,
    'displaylogo': False,
    'doubleClick': 'reset',
    'scrollZoom': False,   # would fight page scroll on a phone
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
}


def get_mobile_config():
    """Plotly interaction config, shared by every chart including the grid."""
    return MOBILE_CONFIG


def get_mobile_layout(chart_type='default'):
    """Layout defaults for a chart type.

    A deep copy: the axis dicts are shared between chart types, so a shallow
    copy would let one caller's mutation of layout["xaxis"] leak into every
    later chart in the process.
    """
    return copy.deepcopy(CHART_CONFIGS.get(chart_type, MOBILE_LAYOUT_DEFAULTS))


def apply_mobile_optimization(fig, chart_type='default'):
    """Apply the shared layout and a legible tooltip."""
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
    """Render a figure with the shared layout and interaction config."""
    import streamlit as st

    fig = apply_mobile_optimization(fig, chart_type)
    st.plotly_chart(fig, use_container_width=True, config=get_mobile_config())
