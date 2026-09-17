"""
Notable picks, as ranked cards.

These are the app's personality and they used to render as bare dataframes.
Row shaping is pure so the copy rules - pluralisation, badges, and the
no-emoji rule - are testable without a Streamlit runtime.
"""

import html

import streamlit as st

from app.theme import BORDER, INK, INK_MUTED

MAX_CARDS = 5

# A loss that beat the spread is still a loss, and if it took half the pool with
# it that is the story of the week. The floor keeps such a pick on the board
# instead of scoring it zero or negative and sorting it below a one-entrant one.
MIN_SHOCK = 1


def upset_shock(margin, point_spread, was_favorite):
    """How much worse the result was than the market expected, in points.

    A 10-point favourite losing by 12 is a 22-point swing; a 3-point underdog
    losing by 21 is only 18, because 3 of those points were priced in. Ranking
    on raw margin got this exactly backwards - it put a team that was *expected*
    to lose at the top of a list about dumb picks.

    Falls back to the raw margin when no spread was recorded, which is the
    common case: 2025 has odds for 31 of its 240 games, and a week's spreads
    only land once the odds job has run. Without the fallback the section would
    empty out across most of the history.
    """
    if point_spread is None:
        return margin
    return margin + (point_spread if was_favorite else -point_spread)


def dumbness_score(margin, point_spread, was_favorite, eliminated_count):
    """Rank key for the dumbest picks: how wrong it was, times how many it took.

    Owner's definition, chosen over ranking on either factor alone: a pick is
    dumb in proportion to how safe it looked and how much of the pool believed
    it. LAC in 2026 week 1 - a 10-point favourite that lost by 12 and ended 118
    of 300 entrants - is the case this is calibrated against.
    """
    shock = upset_shock(margin, point_spread, was_favorite)
    return max(shock, MIN_SHOCK) * eliminated_count


def _favourite_badge(pick):
    """`10-PT FAVORITE` when the market had the picked team winning.

    Only for favourites: labelling a 3-point underdog is noise, and the whole
    point of the badge is to explain why a 12-point loss outranks a 21-point one.
    """
    spread = pick.get("point_spread")
    if not pick.get("was_favorite") or not spread:
        return []
    points = int(spread) if float(spread).is_integer() else spread
    return [f"{points}-PT FAVORITE"]


def dumbest_card_rows(picks):
    """Shape the worst beatings for display, worst first.

    Order is decided by the caller - `dumbness_score` - not here. The score
    itself is deliberately never shown: "2596" means nothing on a card, while
    the two numbers it is built from mean everything.
    """
    rows = []
    for rank, pick in enumerate(picks[:MAX_CARDS], start=1):
        count = pick["eliminated_count"]
        rows.append({
            "rank": rank,
            "headline": str(pick["margin"]),
            "headline_unit": "point loss",
            "matchup": f"{pick['team']} vs {pick['opponent']}",
            "week": f"Week {pick['week']}",
            "detail": f"{count} player{'' if count == 1 else 's'} eliminated",
            "badges": _favourite_badge(pick),
        })
    return rows


def big_balls_card_rows(picks):
    """Shape the risky wins.

    Leads with matchup and week rather than the underdog framing: 2025 has no
    spread data at all, so `was_underdog` never fires, and a design that led
    with it would look broken across the entire season.
    """
    rows = []
    for rank, pick in enumerate(picks[:MAX_CARDS], start=1):
        road = pick["road_win"]
        badges = []
        if pick.get("was_underdog"):
            badges.append("UNDERDOG")
        if road:
            badges.append("ROAD")
        count = pick["big_balls_count"]
        rows.append({
            "rank": rank,
            "headline": str(count),
            "headline_unit": f"player{'' if count == 1 else 's'} survived it",
            "matchup": f"{pick['team']} {'at' if road else 'vs'} {pick['opponent']}",
            "week": f"Week {pick['week']}",
            "detail": "",
            "badges": badges,
        })
    return rows


def _badges_html(badges, tone):
    return " ".join(
        f'<span class="badge {tone}">{html.escape(b)}</span>' for b in badges
    )


def _render_hero(row, tone):
    st.markdown(
        f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;
                      align-items:baseline;gap:.5rem;">
            <div class="kpi-label">{html.escape(row['matchup'])}</div>
            <div class="kpi-label">{html.escape(row['week'])}</div>
          </div>
          <div style="font-size:2.8rem;font-weight:800;line-height:1.05;
                      color:{INK};font-variant-numeric:tabular-nums;
                      margin:.15rem 0;">
            {html.escape(row['headline'])}<span style="font-size:.85rem;
              font-weight:600;color:{INK_MUTED};margin-left:.4rem;">
              {html.escape(row['headline_unit'])}</span>
          </div>
          <div class="kpi-sub">{html.escape(row['detail'])}
            {_badges_html(row['badges'], tone)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_row(row, tone):
    st.markdown(
        f"""
        <div style="display:flex;align-items:baseline;gap:.6rem;
                    padding:.45rem .2rem;border-bottom:1px solid {BORDER};">
          <span style="color:{INK_MUTED};font-size:.78rem;width:1.2rem;
                       flex:none;">{row['rank']}</span>
          <span style="color:{INK};font-weight:600;flex:1 1 auto;
                       min-width:0;">{html.escape(row['matchup'])}</span>
          <span style="color:{INK_MUTED};font-size:.78rem;flex:none;">
            {html.escape(row['week'])}</span>
          <span style="color:{INK};font-weight:700;flex:none;
                       font-variant-numeric:tabular-nums;">
            {html.escape(row['headline'])}</span>
          {_badges_html(row['badges'], tone)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_panel(title, subtitle, rows, empty_message, tone):
    st.markdown(f'<div class="eyebrow">{html.escape(title)}</div>',
                unsafe_allow_html=True)
    st.caption(subtitle)
    if not rows:
        st.info(empty_message)
        return
    _render_hero(rows[0], tone)
    for row in rows[1:]:
        _render_row(row, tone)


def render_meme_stats(meme_stats):
    """Render both notable-picks panels."""
    st.markdown('<div class="section-title">Notable picks</div>',
                unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        _render_panel(
            "Dumbest picks",
            "The worst beatings anyone walked into.",
            dumbest_card_rows(meme_stats.get("dumbest_picks", [])),
            "No eliminations yet. This ranks the worst beatings once picks "
            "start losing.",
            "danger",
        )
    with right:
        _render_panel(
            "Big balls",
            "Road wins and underdog wins that paid off.",
            big_balls_card_rows(meme_stats.get("big_balls_picks", [])),
            "No risky wins yet. Road wins and underdog wins land here once "
            "week 1 is final.",
            "win",
        )
