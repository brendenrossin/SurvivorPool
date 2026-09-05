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


def dumbest_card_rows(picks):
    """Shape the worst beatings for display, worst first."""
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
            "badges": [],
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
