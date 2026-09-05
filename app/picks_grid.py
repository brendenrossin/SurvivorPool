"""
Weekly Picks Grid

A team x week grid that leads with the current week. Rows are the teams picked
this week, ordered by this week's count. The current week's cells carry the team
colour, lifted where it does not clear the emphasis floor against the surface;
earlier weeks recede into a muted version of it; and a pick busted this week is
desaturated and given a danger border.

Replaces the stacked bar chart, which encoded 30 teams as 30 competing colours.
Because colour here carries identity rather than magnitude, every cell shows its
number.
"""

from typing import Dict, Iterable, List, Optional, Tuple

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


def aggregate_picks(
    summary_weeks: List[Dict], current_week: int
) -> Tuple[Dict[Tuple[int, str], int], Dict[int, int], Dict[str, int]]:
    """Roll `summary["weeks"]` up into the grid's three lookups.

    Everything after `current_week` is dropped here, and this is the only place
    it is dropped: the sheet holds picks for weeks that have not kicked off, and
    rendering them would publish next week's picks. Because `season_totals` is
    built from the same clipped pass, a team picked only in a future week cannot
    reach the grid as a padded row either.

    Args:
        summary_weeks: [{"week": int, "teams": [{"team": str, "count": int}]}]
        current_week: the last week that has kicked off

    Returns:
        ({(week, team): picks}, {week: picks that week}, {team: picks so far})
    """
    counts: Dict[Tuple[int, str], int] = {}
    week_totals: Dict[int, int] = {}
    season_totals: Dict[str, int] = {}

    for week_data in summary_weeks:
        week = week_data["week"]
        if week > current_week:
            continue
        for team_item in week_data["teams"]:
            team, count = team_item["team"], team_item["count"]
            counts[(week, team)] = counts.get((week, team), 0) + count
            week_totals[week] = week_totals.get(week, 0) + count
            season_totals[team] = season_totals.get(team, 0) + count

    return counts, week_totals, season_totals


def resolve_current_week(
    pick_weeks: Iterable[int], started_game_weeks: Iterable[int]
) -> int:
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

    # The latest week that has picks *and* has kicked off. Taking
    # min(max(started), max(pick_weeks)) instead would return a week that has no
    # picks whenever the pick weeks have a gap - the grid would then bold a
    # column that isn't drawn and lead with no full-colour cell at all.
    kicked_off = max(started)
    eligible = [w for w in pick_weeks if w <= kicked_off]
    return max(eligible) if eligible else min(pick_weeks)


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


INKS = ("#0b0b0b", "#ffffff")


def label_ink(hex_color: str) -> str:
    """Text colour that stays legible on `hex_color`.

    Picks whichever ink actually yields more contrast rather than thresholding
    luminance. The old threshold was 0.45; the real crossover where dark ink
    overtakes white is 0.1791 - solve 1.05/(L+0.05) = (L+0.05)/0.05 - so every
    fill in between took white ink where black reads better. That put five
    teams under the 4.5:1 small-text floor: CIN and DEN #FB4F14 at 3.37:1,
    MIA #008E97 at 3.95:1, CAR #0085CA at 4.03:1, LAC #0080C6 at 4.28:1.

    This module says contrast is computed, never assumed. The threshold was the
    assumption.
    """
    return max(INKS, key=lambda ink: contrast_ratio(ink, hex_color))


def _share_label(share: float) -> str:
    """Percent label that never rounds a real pick down to "0%"."""
    if 0 < share < 0.5:
        return "<1%"
    return f"{share:.0f}%"


def mute_color(hex_color: str, background: str, amount: float = HISTORY_MIX) -> str:
    """Blend `hex_color` toward `background`, keeping `amount` of the original."""
    blended = (
        round(c * amount + b * (1 - amount))
        for c, b in zip(_channels(hex_color), _channels(background))
    )
    return "#{:02x}{:02x}{:02x}".format(*blended)


# Semantic danger hue. Consumed as a HUE ANCHOR rather than as a literal border
# colour: the border sits on a fill this module chooses, not on the app surface,
# so its lightness is adjusted per-fill by ensure_contrast(). Swap for
# app.theme.DANGER when it lands.
DANGER = "#B91C1C"

WCAG_GRAPHIC_MIN = 3.0   # WCAG 2.1 non-text contrast floor


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_contrast(
    color: str, against: str, minimum: float = WCAG_GRAPHIC_MIN
) -> str:
    """Move `color` toward white or black until it clears `minimum`.

    The danger token is chosen against the app surface, but this border sits on
    a desaturated fill instead - a different contrast question with a different
    answer. Rather than keeping a second token in step by hand, the lightness is
    computed. A no-op whenever the token already clears.
    """
    if contrast_ratio(color, against) >= minimum:
        return color

    # Move away from the fill: darken on a light fill, lighten on a dark one.
    # Twenty 5% steps reach pure black or white, so this always terminates.
    toward = "#000000" if relative_luminance(against) > relative_luminance(color) else "#ffffff"
    for step in range(1, 21):
        candidate = mute_color(color, toward, 1 - step * 0.05)
        if contrast_ratio(candidate, against) >= minimum:
            return candidate
    return toward


def _grey_at(luminance: float) -> str:
    """The achromatic colour with this WCAG relative luminance."""
    if luminance <= 0.0031308:
        channel = 12.92 * luminance
    else:
        channel = 1.055 * (luminance ** (1 / 2.4)) - 0.055
    value = max(0, min(255, round(channel * 255)))
    return "#{0:02x}{0:02x}{0:02x}".format(value)


ELIMINATED_LUMA = 0.42     # luminance every busted cell converges toward
ELIMINATED_CONVERGE = 0.55  # how far toward it


def eliminated_fill(hex_color: str, background: str) -> str:
    """Fill for a current-week pick whose game is lost.

    Drops hue entirely and pulls luminance toward a shared mid target, so every
    busted cell lands on roughly the same grey. That is deliberate: elimination
    is a shared fate, and identity already lives in the row label rather than
    in the fill.

    History mutes on LIGHTNESS and keeps hue; this mutes on SATURATION. Two
    different axes, which is what stops the grid's primary encoding collapsing
    - muted colour already means "an earlier week".

    Converging toward the middle rather than holding history's own lightness is
    what makes it read. Holding it stated the axes argument more purely but put
    the fill at the same luminance as the pale history band on a light surface,
    leaving the border to carry the whole signal. The mid target is also why no
    surface branch is needed: it sits far from a light surface and far from a
    dark one, so it separates on both.

    `background` is accepted for symmetry with mute_color and so a future
    surface-dependent rule is not an API change.
    """
    lum = (
        relative_luminance(hex_color) * (1 - ELIMINATED_CONVERGE)
        + ELIMINATED_LUMA * ELIMINATED_CONVERGE
    )
    return _grey_at(lum)


def eliminated_edge(fill: str, danger: str = DANGER) -> str:
    """Border for a busted cell: the danger hue, made legible on `fill`."""
    return ensure_contrast(danger, fill)


def _to_hsl(hex_color: str) -> Tuple[float, float, float]:
    r, g, b = (c / 255 for c in _channels(hex_color))
    high, low = max(r, g, b), min(r, g, b)
    lightness = (high + low) / 2
    if high == low:
        return 0.0, 0.0, lightness
    delta = high - low
    sat = delta / (2 - high - low) if lightness > 0.5 else delta / (high + low)
    if high == r:
        hue = ((g - b) / delta) % 6
    elif high == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    return hue / 6, sat, lightness


def _from_hsl(hue: float, sat: float, lightness: float) -> str:
    if sat == 0:
        channel = round(lightness * 255)
        return "#{0:02x}{0:02x}{0:02x}".format(channel)
    q = lightness * (1 + sat) if lightness < 0.5 else lightness + sat - lightness * sat
    p = 2 * lightness - q

    def component(t: float) -> int:
        t = t % 1
        if t < 1 / 6:
            value = p + (q - p) * 6 * t
        elif t < 1 / 2:
            value = q
        elif t < 2 / 3:
            value = p + (q - p) * (2 / 3 - t) * 6
        else:
            value = p
        return max(0, min(255, round(value * 255)))

    return "#{:02x}{:02x}{:02x}".format(
        component(hue + 1 / 3), component(hue), component(hue - 1 / 3)
    )


def contrast_fill(color: str, background: str, target: float = WCAG_GRAPHIC_MIN) -> str:
    """Move `color`'s lightness until it clears `target` against `background`.

    Bidirectional and hue-preserving: it lightens on a dark surface and darkens
    on a light one, and moves only as far as the floor requires, so a team that
    already clears is returned untouched.

    This exists because the grid's emphasis channel is bounded by the distance
    from a team's colour to the surface. The current week carries true team
    colour and earlier weeks recede to mute_color(); on #0B1220 a dark team has
    nowhere to recede to, and CIE76 dE between CHI's current and muted cells
    falls to 3.5 - about the just-noticeable threshold - so the grid stops
    leading with the current week, which is its entire purpose. Lifting the
    emphasised end is the only direction with headroom: raising HISTORY_MIX
    moves muted toward true, and lowering it pins muted to the surface.

    A wholly achromatic team cannot keep a hue it does not have, so LV #000000
    lifts to a grey. Black cannot be shown on black; that is the accepted cost.
    """
    if contrast_ratio(color, background) >= target:
        return color

    # Try both directions and take whichever clears with the smaller move,
    # rather than picking a direction from a luminance threshold. label_ink
    # used to guess that way and was wrong for five teams; a threshold here
    # would be the same mistake, and on a mid-luminance surface it picks the
    # direction with no headroom and returns a colour that misses the target
    # the function promises.
    hue, sat, lightness = _to_hsl(color)
    reached = []
    for direction in (1, -1):
        for step in range(1, 101):
            moved = lightness + direction * step / 100
            if not 0 <= moved <= 1:
                break
            candidate = _from_hsl(hue, sat, moved)
            if contrast_ratio(candidate, background) >= target:
                reached.append((step, candidate))
                break

    if reached:
        return min(reached)[1]
    # Neither direction can reach it - the surface is mid-luminance. Give back
    # whichever endpoint is furthest from it rather than a silent failure.
    return max(("#ffffff", "#000000"), key=lambda c: contrast_ratio(c, background))


DISSOLVE_RATIO = 1.35    # below this a fill and the surface read as one block
HISTORY_INK_MIX = 0.72   # how much of full-contrast ink history keeps


def cell_edge(fill: str, background: str) -> str:
    """Hairline that stops a cell dissolving into the surface.

    The old rule drew a dark hairline when the fill's luminance cleared 0.6 -
    correct only because the app was light-only. A light fill on a light surface
    and a dark fill on a dark one are the same problem, so the test is against
    the surface rather than against a fixed threshold, and the hairline takes
    whichever side the surface is not on.
    """
    if contrast_ratio(fill, background) >= DISSOLVE_RATIO:
        return fill
    return "rgba(0,0,0,.18)" if relative_luminance(background) > 0.45 else "rgba(255,255,255,.28)"


def history_ink(fill: str) -> str:
    """Label ink for an earlier week's cell.

    Deliberately softer than label_ink(): history should recede, and computing
    full contrast here would darken it and cost the recede effect. It was
    hardcoded "#52514e" - a dark ink, correct on the light surface it was
    written for and invisible on a dark one.
    """
    return mute_color(label_ink(fill), fill, HISTORY_INK_MIX)


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
    team_status: Optional[Dict[str, str]] = None,
    danger: str = DANGER,
    current_week_min_contrast: Optional[float] = None,
) -> go.Figure:
    """Build the picks grid figure.

    Cells are drawn as layout shapes so they scale with the plot, with an
    invisible scatter trace supplying hover and annotations supplying the
    numbers.

    Args:
        weeks: weeks to display, ascending, ending at `current_week`
        rows: ordered team abbreviations (see `select_grid_rows`)
        counts: {(week, team): picks}
        week_totals: {week: picks that week}
        team_colors: {team: hex}
        current_week: the week drawn in full colour
        as_percent: label cells with share of the week instead of raw count
        background: surface colour that earlier weeks blend toward
        team_names: {team: full name} for the tooltip
        team_status: {team: 'won'|'lost'|'pending'} for `current_week`. A team
            marked 'lost' takes the eliminated treatment, in the current week
            only - history's job here is volume, not outcome. None renders
            exactly as before.
        danger: semantic danger hue for the eliminated border.
        current_week_min_contrast: when non-zero, lift the current week's fills
            to clear this contrast ratio against `background`. The grid's
            emphasis is bounded by team-colour-to-surface distance, so on a
            dark surface a dark team has nowhere for its history to recede to.
            History is deliberately NOT lifted - that would close the gap this
            opens. None leaves fills at true team colour.
    """
    team_names = team_names or {}
    team_status = team_status or {}
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
            is_out = is_now and team_status.get(team) == "lost"
            total = week_totals.get(week, 0)
            share = (100 * n / total) if total else 0

            if is_out:
                fill = eliminated_fill(base, background)
                edge, edge_width, ink = eliminated_edge(fill, danger), 2, label_ink(fill)
            elif is_now:
                fill = (
                    contrast_fill(base, background, current_week_min_contrast)
                    if current_week_min_contrast else base
                )
                edge, edge_width, ink = cell_edge(fill, background), 1, label_ink(fill)
            else:
                fill = muted
                edge, edge_width, ink = cell_edge(fill, background), 1, history_ink(fill)

            shapes.append(dict(
                type="rect", xref="x", yref="y",
                x0=col_idx - CELL_W / 2, x1=col_idx + CELL_W / 2,
                y0=row_idx - CELL_H / 2, y1=row_idx + CELL_H / 2,
                fillcolor=fill,
                line=dict(width=edge_width, color=edge),
                layer="below",
            ))

            annotations.append(dict(
                x=col_idx, y=row_idx,
                text=_share_label(share) if as_percent else str(n),
                showarrow=False,
                font=dict(
                    size=12 if is_now else 11,
                    color=ink,
                    family="Inter, system-ui",
                ),
            ))

            hx.append(col_idx)
            hy.append(row_idx)
            if is_out:
                state = f"<br><b>Eliminated</b> — {n} out"
            elif is_now:
                state = " (current)"
            else:
                state = ""
            hover.append(
                f"<b>{team_names.get(team, team)}</b><br>"
                f"Week {week}{state}<br>"
                f"{n} of {total} picks — {share:.1f}%"
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
        # The margins are a floor, not the budget: `automargin` grows them to fit
        # the team labels on the left and the week labels along the top. Without
        # it both are clipped to their last character.
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(
            side="top", range=[-0.6, len(weeks) - 0.4],
            tickmode="array", tickvals=list(range(len(weeks))),
            ticktext=[
                f"<b>W{w}</b>" if w == current_week else f"W{w}" for w in weeks
            ],
            showgrid=False, zeroline=False, fixedrange=True, automargin=True,
        ),
        yaxis=dict(
            range=[len(rows) - 0.4, -0.6],  # reversed explicitly; see note above
            tickmode="array", tickvals=list(range(len(rows))), ticktext=rows,
            showgrid=False, zeroline=False, fixedrange=True, automargin=True,
        ),
        # Derived from the surface, not hardcoded light: omitting the font
        # colour is what made the old tooltip render near-white on white, and
        # hardcoding it merely moves that bug to the other theme.
        hoverlabel=dict(
            bgcolor=background,
            bordercolor=mute_color(label_ink(background), background, 0.25),
            font=dict(color=label_ink(background), size=12, family="Inter, system-ui"),
            align="left",
        ),
    )
    return fig
