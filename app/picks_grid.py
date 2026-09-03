"""
Weekly Picks Grid

A team x week grid that leads with the current week. Rows are the teams picked
this week, ordered by this week's count; the current week's cells carry the true
team colour and earlier weeks recede into a muted version of it.

Replaces the stacked bar chart, which encoded 30 teams as 30 competing colours.
Because colour here carries identity rather than magnitude, every cell shows its
number.
"""

from typing import Dict, List, Optional, Tuple

import plotly.graph_objects as go

# Cell geometry, in data coordinates (1.0 = one grid step)
CELL_W, CELL_H = 0.92, 0.82
ROW_PX = 34          # vertical space per team row
CHROME_PX = 120      # axis labels, title, margins

MIN_ROWS = 10
HISTORY_MIX = 0.26   # how much team colour survives in an earlier week's cell


def select_grid_rows(
    week_counts: Dict[str, int],
    season_totals: Dict[str, int],
    min_rows: int = MIN_ROWS,
    expanded: bool = False,
) -> List[str]:
    """Choose and order the grid's team rows.

    Teams picked in the current week come first, ordered by that week's count.
    Remaining slots are filled by season total until `min_rows` is reached, so a
    quiet week still renders a full-looking grid. There is no upper limit - a
    week with 16 distinct picks shows 16 rows.

    Args:
        week_counts: {team: picks} for the current week
        season_totals: {team: picks} across every week so far
        min_rows: floor on row count; ignored when `expanded`
        expanded: show every team picked so far instead of just the top slice

    Returns:
        Ordered list of team abbreviations.
    """
    picked = sorted(
        week_counts,
        key=lambda t: (-week_counts[t], -season_totals.get(t, 0), t),
    )
    rest = sorted(
        (t for t in season_totals if t not in week_counts),
        key=lambda t: (-season_totals[t], t),
    )

    if expanded:
        return picked + rest

    fill = max(0, max(min_rows, len(picked)) - len(picked))
    return picked + rest[:fill]


def resolve_current_week(pick_weeks, started_game_weeks) -> int:
    """The week the grid should lead with.

    Picks are entered in the sheet weeks ahead of kickoff, so the latest week
    holding a pick is not "now". The current week is the latest week whose games
    have actually started, clamped to the weeks that have picks (the NFL
    schedule runs past the pool's final week).

    Args:
        pick_weeks: every week with at least one pick
        started_game_weeks: every week with at least one game underway or final

    Returns:
        The week to draw in full colour; 1 before the season starts.
    """
    pick_weeks = list(pick_weeks)
    started = list(started_game_weeks)

    if not pick_weeks:
        return 1
    if not started:
        return min(pick_weeks)

    return min(max(started), max(pick_weeks))


def _channels(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of a hex colour."""
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _channels(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def label_ink(hex_color: str) -> str:
    """Text colour that stays legible on `hex_color`.

    Computed, never assumed - team colours run from LV black to PIT gold, and
    assuming one ink is how the tooltip ended up white-on-white.
    """
    return "#0b0b0b" if relative_luminance(hex_color) > 0.45 else "#ffffff"


def mute_color(hex_color: str, background: str, amount: float = HISTORY_MIX) -> str:
    """Blend `hex_color` toward `background`, keeping `amount` of the original."""
    blended = (
        round(c * amount + b * (1 - amount))
        for c, b in zip(_channels(hex_color), _channels(background))
    )
    return "#{:02x}{:02x}{:02x}".format(*blended)


def build_picks_grid(
    weeks: List[int],
    rows: List[str],
    counts: Dict[Tuple[int, str], int],
    week_totals: Dict[int, int],
    team_colors: Dict[str, str],
    current_week: int,
    as_percent: bool = False,
    background: str = "#ffffff",
    team_names: Optional[Dict[str, str]] = None,
) -> go.Figure:
    """Build the picks grid figure.

    Cells are drawn as layout shapes so they scale with the plot, with an
    invisible scatter trace supplying hover and annotations supplying the
    numbers.

    Args:
        weeks: weeks to display, ascending, ending at `current_week`
        rows: ordered team abbreviations (see `select_grid_rows`)
        counts: {(week, team): picks}
        week_totals: {week: surviving entrants that week}
        team_colors: {team: hex}
        current_week: the week drawn in full colour
        as_percent: label cells with share of the week instead of raw count
        background: surface colour that earlier weeks blend toward
        team_names: {team: full name} for the tooltip
    """
    team_names = team_names or {}
    fig = go.Figure()

    shapes, annotations = [], []
    hx, hy, hover = [], [], []

    for row_idx, team in enumerate(rows):
        base = team_colors.get(team, "#666666")
        muted = mute_color(base, background)

        for col_idx, week in enumerate(weeks):
            n = counts.get((week, team), 0)
            if not n:
                continue

            is_now = week == current_week
            fill = base if is_now else muted
            total = week_totals.get(week, 0)
            share = (100 * n / total) if total else 0

            shapes.append(dict(
                type="rect", xref="x", yref="y",
                x0=col_idx - CELL_W / 2, x1=col_idx + CELL_W / 2,
                y0=row_idx - CELL_H / 2, y1=row_idx + CELL_H / 2,
                fillcolor=fill,
                line=dict(width=1, color="rgba(0,0,0,.12)" if relative_luminance(fill) > 0.6 else fill),
                layer="below",
            ))

            annotations.append(dict(
                x=col_idx, y=row_idx,
                text=f"{share:.0f}%" if as_percent else str(n),
                showarrow=False,
                font=dict(
                    size=12 if is_now else 11,
                    color=label_ink(fill) if is_now else "#52514e",
                    family="Inter, system-ui",
                ),
            ))

            hx.append(col_idx)
            hy.append(row_idx)
            hover.append(
                f"<b>{team_names.get(team, team)}</b><br>"
                f"Week {week}{' (current)' if is_now else ''}<br>"
                f"{n} of {total} survivors — {share:.1f}%"
            )

    # Invisible markers carry the hover layer; the shapes carry the colour.
    fig.add_trace(go.Scatter(
        x=hx, y=hy, mode="markers",
        marker=dict(size=26, opacity=0, color="rgba(0,0,0,0)"),
        hovertext=hover, hoverinfo="text", showlegend=False,
    ))

    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        height=len(rows) * ROW_PX + CHROME_PX,
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(
            side="top", range=[-0.6, len(weeks) - 0.4],
            tickmode="array", tickvals=list(range(len(weeks))),
            ticktext=[
                f"<b>W{w}</b>" if w == current_week else f"W{w}" for w in weeks
            ],
            showgrid=False, zeroline=False, fixedrange=True,
        ),
        yaxis=dict(
            autorange="reversed", range=[-0.6, len(rows) - 0.4],
            tickmode="array", tickvals=list(range(len(rows))), ticktext=rows,
            showgrid=False, zeroline=False, fixedrange=True,
        ),
        # Explicit ink - omitting font colour is what made the old tooltip
        # render near-white on white.
        hoverlabel=dict(
            bgcolor="#ffffff", bordercolor="#d3d6dc",
            font=dict(color="#0b0b0b", size=12, family="Inter, system-ui"),
            align="left",
        ),
    )
    return fig
