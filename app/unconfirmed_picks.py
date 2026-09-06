#!/usr/bin/env python3
"""This week's picks, pulled from the GroupMe before they are confirmed.

Entrants post picks to the group days before they are entered officially, so
the shape of the week is knowable early: is everyone piling onto the same team
again? That question is what this widget answers. It is not an attribution -
who picked what is answered later, and authoritatively, by the picks grid above
it.

The count undershoots on purpose. Only unambiguous declarations parse (84.9% of
the sheet across 2025), because the alternative - loosening the parser until
"good luck boys" becomes a Dallas pick - makes a number nobody can trust. A
tally that admits it is partial is honest; one that misattributes is not.

Copy rules, from the owner: say "pulled from GroupMe", never "the sheet" -
nobody reading the dashboard knows what the sheet is.
"""

import html
from typing import Any, Dict, List, Mapping

import streamlit as st

from app.dashboard_data import get_unconfirmed_tally, load_team_data
from app.theme import BORDER, INK_MUTED, SURFACE, contrast_fill

MANAGER = "Trav"
FALLBACK_COLOR = "#666666"
MAX_ROWS = 8


def build_tally_view(data: Mapping[str, Any],
                     colors: Mapping[str, str]) -> Dict[str, Any]:
    """Turn the cached tally into everything the markup needs.

    Kept free of Streamlit so the copy and the bar geometry can be asserted
    directly - what the widget says is the part most worth testing.
    """
    week = data.get("week")
    teams: List[tuple] = list(data.get("teams") or [])
    unconfirmed = int(data.get("unconfirmed") or 0)
    confirmed = int(data.get("confirmed") or 0)
    empty = week is None or not teams

    biggest = max((count for _, count in teams), default=0)
    rows = [{
        "team": team,
        "count": count,
        "pct": 100.0 * count / biggest if biggest else 0.0,
        "color": contrast_fill(colors.get(team) or FALLBACK_COLOR, SURFACE),
    } for team, count in teams[:MAX_ROWS]]

    # The jab only fires when it is true. If the manager is current there is no
    # joke to make, and a bit resting on a false premise is worse than none.
    jab = not empty and unconfirmed > confirmed

    if empty:
        caption = ("No picks spotted in the GroupMe for this week yet.")
    elif jab:
        caption = (f"{unconfirmed} picks pulled from GroupMe while we wait for "
                   f"{MANAGER} to officially update picks.")
    else:
        caption = ("Pulled from GroupMe. Unofficial until picks are confirmed.")

    return {
        "week": week,
        "empty": empty,
        "jab": jab,
        "rows": rows,
        "caption": caption,
        "heading": f"Week {week} picks, pulled from GroupMe" if week
                   else "Picks pulled from GroupMe",
        "unconfirmed": unconfirmed,
        "confirmed": confirmed,
        "unconfirmed_label": "Pulled from GroupMe",
        "confirmed_label": "Confirmed",
    }


def _view_html(view: Mapping[str, Any]) -> str:
    """The whole widget as one markdown block.

    One st.markdown rather than a column per team: Streamlit columns wrap on a
    phone, and this sits directly under the picks grid where a reflow would
    read as part of it.
    """
    bars = "".join(
        f'<div class="up-row">'
        f'<span class="up-team">{html.escape(row["team"])}</span>'
        f'<span class="up-track">'
        f'<span class="up-bar" style="width:{row["pct"]:.1f}%;'
        f'background:{row["color"]}"></span></span>'
        f'<span class="up-count">{row["count"]}</span>'
        f'</div>'
        for row in view["rows"])

    return f"""
<div class="up-wrap">
  <div class="up-head">{html.escape(view["heading"])}</div>
  <div class="up-nums">
    <div class="up-num">
      <div class="up-big">{view["unconfirmed"]}</div>
      <div class="up-cap">{html.escape(view["unconfirmed_label"])}</div>
    </div>
    <div class="up-num">
      <div class="up-big up-dim">{view["confirmed"]}</div>
      <div class="up-cap">{html.escape(view["confirmed_label"])}</div>
    </div>
  </div>
  <div class="up-bars">{bars}</div>
  <div class="up-foot">{html.escape(view["caption"])}</div>
</div>
<style>
.up-wrap {{ border:1px solid {BORDER}; border-radius:12px; padding:14px 16px; }}
.up-head {{ font-weight:600; font-size:0.95rem; margin-bottom:10px; }}
.up-nums {{ display:flex; gap:28px; margin-bottom:12px; }}
.up-big {{ font-size:1.6rem; font-weight:700; line-height:1.1; }}
.up-dim {{ color:{INK_MUTED}; }}
.up-cap {{ font-size:0.72rem; color:{INK_MUTED}; text-transform:uppercase;
           letter-spacing:0.04em; }}
.up-row {{ display:flex; align-items:center; gap:8px; margin:3px 0; }}
.up-team {{ width:42px; font-size:0.78rem; font-variant-numeric:tabular-nums;
            color:{INK_MUTED}; }}
.up-track {{ flex:1; height:10px; border-radius:5px;
             background:rgba(255,255,255,0.06); overflow:hidden; }}
.up-bar {{ display:block; height:100%; border-radius:5px; }}
.up-count {{ width:26px; text-align:right; font-size:0.78rem;
             font-variant-numeric:tabular-nums; }}
.up-foot {{ margin-top:10px; font-size:0.78rem; color:{INK_MUTED}; }}
</style>
"""


def render_unconfirmed_picks_widget(season: int) -> bool:
    """Draw the widget; return whether anything was drawn.

    Silence is the right empty state here. This sits between the two things
    people actually come for, and an empty card between them is worse than no
    card - see docs/design/groupme-recap-spec.md on placement.

    The return value exists so the caller can own the spacing around it: a
    widget that drew nothing must not leave a second divider stacked against
    the picks grid's.
    """
    try:
        data = get_unconfirmed_tally(season)
    except Exception as exc:  # pragma: no cover - defensive, as elsewhere
        st.warning(f"⚠️ Could not read GroupMe picks: {exc}")
        return False

    colors = {team: meta.get("color", FALLBACK_COLOR)
              for team, meta in load_team_data()["teams"].items()}
    view = build_tally_view(data, colors)
    if view["empty"]:
        return False

    st.markdown(_view_html(view), unsafe_allow_html=True)
    return True
