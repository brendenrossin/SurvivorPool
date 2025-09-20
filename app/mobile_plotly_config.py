"""
Mobile-Optimized Plotly Configuration
Focus on touch interactions only, remove heavy features
"""

# Mobile-optimized Plotly configuration
MOBILE_CONFIG = {
    # Remove all toolbar buttons except zoom/pan
    'displayModeBar': False,  # Hide toolbar completely for cleaner mobile UI
    'displaylogo': False,
    'modeBarButtonsToRemove': [
        'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
        'autoScale2d', 'resetScale2d', 'hoverClosestCartesian',
        'hoverCompareCartesian', 'zoom2d', 'toggleSpikelines',
        'toImage', 'sendDataToCloud'
    ],
    'doubleClick': 'reset',  # Double tap to reset view
    'scrollZoom': False,  # Disable scroll zoom to prevent conflicts with page scroll
    'responsive': True,  # Auto-resize for mobile
    'staticPlot': False,  # Keep touch interactions
}

# Mobile-optimized layout defaults
MOBILE_LAYOUT_DEFAULTS = {
    'margin': {'l': 20, 'r': 20, 't': 40, 'b': 40},  # Minimal margins for mobile
    'font': {'size': 12},  # Readable font size on mobile
    'showlegend': False,  # Legends take up too much space on mobile
    'hovermode': 'closest',  # Better touch targeting
    'dragmode': False,  # Disable drag to prevent scroll conflicts
    'paper_bgcolor': 'rgba(0,0,0,0)',  # Transparent background
    'plot_bgcolor': 'rgba(0,0,0,0)',
}

# Chart-specific mobile configurations
CHART_CONFIGS = {
    'donut': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 250,  # Compact for mobile
        'showlegend': True,  # Exception: donut needs legend
        'legend': {
            'orientation': "h",  # Horizontal legend
            'yanchor': "bottom",
            'y': -0.1,
            'xanchor': "center",
            'x': 0.5,
            'font': {'size': 10}
        }
    },

    'bar_chart': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 300,
        'xaxis': {
            'tickfont': {'size': 10},
            'title': {'font': {'size': 11}}
        },
        'yaxis': {
            'tickfont': {'size': 10},
            'title': {'font': {'size': 11}}
        }
    },

    'line_chart': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 300,
        'xaxis': {
            'tickfont': {'size': 10},
            'title': {'font': {'size': 11}}
        },
        'yaxis': {
            'tickfont': {'size': 10},
            'title': {'font': {'size': 11}}
        }
    },

    'gauge': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 250,  # Compact gauge
        'margin': {'l': 10, 'r': 10, 't': 30, 'b': 10},
    },

    'heatmap': {
        **MOBILE_LAYOUT_DEFAULTS,
        'height': 250,  # Compact heatmap
        'xaxis': {
            'tickfont': {'size': 9},
            'title': {'font': {'size': 10}}
        },
        'yaxis': {
            'tickfont': {'size': 9},
            'title': {'font': {'size': 10}}
        }
    }
}

def get_mobile_config():
    """Get mobile-optimized Plotly config"""
    return MOBILE_CONFIG

def get_mobile_layout(chart_type='default'):
    """Get mobile-optimized layout for specific chart type"""
    return CHART_CONFIGS.get(chart_type, MOBILE_LAYOUT_DEFAULTS).copy()

def apply_mobile_optimization(fig, chart_type='default'):
    """Apply mobile optimizations to a Plotly figure"""
    layout = get_mobile_layout(chart_type)
    fig.update_layout(**layout)

    # Additional mobile optimizations (skip hover for gauge/indicator charts)
    if chart_type != 'gauge':
        fig.update_traces(
            # Increase hover target area for better touch interaction
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font_size=12
            )
        )

    return fig

def render_mobile_chart(fig, chart_type='default'):
    """Render a Plotly chart with mobile optimizations"""
    import streamlit as st

    # Apply mobile optimizations
    fig = apply_mobile_optimization(fig, chart_type)

    # Render with mobile config
    st.plotly_chart(
        fig,
        use_container_width=True,
        config=get_mobile_config()
    )

# Touch-friendly annotation helpers
def create_touch_annotation(x, y, text, chart_type='bar_chart'):
    """Create touch-friendly annotations for mobile"""
    base_size = 10 if chart_type == 'bar_chart' else 9

    return dict(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        font=dict(size=base_size, color="black"),
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="black",
        borderwidth=1,
        borderpad=2
    )

# Color schemes optimized for mobile (high contrast)
MOBILE_COLORS = {
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'success': '#2ca02c',
    'danger': '#d62728',
    'warning': '#ff7f0e',
    'info': '#17a2b8',
    'eliminated': '#d62728',
    'remaining': '#2ca02c',
    'neutral': '#7f7f7f'
}

def get_mobile_color_scheme():
    """Get high-contrast color scheme for mobile"""
    return MOBILE_COLORS