#!/usr/bin/env python3
"""Live scores — the week's games as a grid of cards.

What separates this from any scoreboard is the second line of every card: how
many entrants are riding on each team, and what just happened to them. That is
the reason anyone opens this page instead of ESPN's.

Data comes from the database only. API calls happen in the cron jobs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pytz
import streamlit as st

from app.dashboard_data import get_week_scoreboard
from app.odds_helpers import format_pregame_line

PACIFIC = pytz.timezone("America/Los_Angeles")

# Live first, then upcoming, then settled; within a status, by kickoff.
#
# There is deliberately no "picked games first" tiebreak: has_picks is uniform
# across every card in each reachable state. When picks are revealed and any
# exist, the filter has already dropped the games nobody picked; otherwise no
# card carries picks at all. A tiebreak on it could never discriminate.
STATUS_ORDER = {"in": 0, "pre": 1, "final": 2}


def resolve_scoreboard_week(
    current_week: int, week_statuses: Dict[int, List[str]]
) -> int:
    """The week the scoreboard should show.

    Deliberately NOT the grid's `resolve_current_week`. The grid leads with the
    last week that kicked off, because that is the last week whose picks may be
    published. The scoreboard rolls forward once a week is finished, so Tuesday
    shows the upcoming slate rather than a settled one.

    The roll is driven by whether the games actually finished. The rule this
    replaces added a week every Tuesday after 04:00 UTC whether or not anything
    had been played, on top of a base week derived as max(Game.week) - which in
    2025 is week 16, a week nobody played, because the NFL schedule outruns the
    pool.
    """
    statuses = week_statuses.get(current_week)
    if not statuses or not all(status == "final" for status in statuses):
        return current_week
    return current_week + 1 if (current_week + 1) in week_statuses else current_week


def should_reveal_picks(scoreboard_week: int, started_weeks: Iterable[int]) -> bool:
    """Whether the scoreboard may show pick data for `scoreboard_week`.

    A week reveals its picks if and only if one of its OWN games has left
    'pre'. Stated that way the invariant is local and unconditional, which is
    the point: the first version derived it by comparing the scoreboard's week
    against the grid's, and that ordering is satisfied in exactly the case it
    most needed to exclude. Before any game of the season has started,
    resolve_current_week falls back to the first week holding picks rather than
    reporting "nothing has started", so both weeks were 1 and 1 <= 1 published
    the entire field's week 1 picks days before kickoff.
    """
    return scoreboard_week in set(started_weeks)


def _as_utc(moment: Optional[datetime]) -> Optional[datetime]:
    """Attach UTC to a naive timestamp; convert - never overwrite - an aware one.

    Postgres returns aware datetimes for Game.kickoff, SQLite (the local dev
    path) returns naive ones. `.replace(tzinfo=utc)` is right for the second
    and silently wrong for the first the moment the session TimeZone is not UTC.
    """
    if moment is None:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _side(team: str, score, winner: Optional[str], status: str,
          picks: int) -> Dict[str, Any]:
    if status == "final" and winner:
        outcome = "won" if winner == team else "lost"
    else:
        outcome = None
    return {"team": team, "score": score, "picks": picks, "outcome": outcome}


def build_scoreboard(
    games: List[Dict[str, Any]],
    pick_counts: Dict[str, int],
    results: Dict[str, Dict[str, int]],
    reveal_picks: bool,
) -> List[Dict[str, Any]]:
    """Card view models for one week.

    `reveal_picks` is false for a week that has not kicked off. It suppresses
    the counts AND the filtering, because filtering the slate down to picked
    teams is itself a disclosure of the field's picks — by omission rather than
    by a number, but the same leak, days before kickoff. So an unplayed week
    shows every game with no pick data at all, and snaps to picked-teams-only
    with counts the moment the week starts.
    """
    cards = []
    for game in games:
        home, away = game["home_team"], game["away_team"]
        home_picks = pick_counts.get(home, 0) if reveal_picks else 0
        away_picks = pick_counts.get(away, 0) if reveal_picks else 0

        # Nobody has picked at all: show the whole slate rather than nothing.
        if reveal_picks and pick_counts and not (home_picks or away_picks):
            continue

        split = results.get(game["game_id"], {}) if reveal_picks else {}
        has_line = game["favorite_team"] and game["point_spread"]
        cards.append({
            "game_id": game["game_id"],
            "status": game["status"],
            "kickoff": game["kickoff"],
            "line": format_pregame_line(
                home, away, game["favorite_team"], game["point_spread"]
            ) if has_line else None,
            "away": _side(away, game["away_score"], game["winner_abbr"],
                          game["status"], away_picks),
            "home": _side(home, game["home_score"], game["winner_abbr"],
                          game["status"], home_picks),
            "has_picks": bool(home_picks or away_picks),
            "eliminated": split.get("eliminated", 0),
            "survived": split.get("survived", 0),
        })

    # game_id last so the order is total. Most of a Sunday slate shares one
    # kickoff, and without it those ties fall back to whatever order the
    # database returned - so cards could shuffle between reruns.
    cards.sort(key=lambda c: (
        STATUS_ORDER.get(c["status"], 3),
        _as_utc(c["kickoff"]) or datetime.min.replace(tzinfo=timezone.utc),
        c["game_id"],
    ))
    return cards


def _status_chip(card: Dict[str, Any]) -> None:
    """Status as a badge. st.badge's colours are theme tokens, not literals."""
    if card["status"] == "in":
        st.badge("LIVE", icon="🔴", color="red")
    elif card["status"] == "final":
        st.badge("FINAL", color="gray")
    elif card["kickoff"]:
        local = _as_utc(card["kickoff"]).astimezone(PACIFIC)
        st.badge(local.strftime("%a %-I:%M %p"), icon="🕐", color="gray")
    else:
        st.badge("TBD", color="gray")


def _team_row(side: Dict[str, Any], status: str) -> None:
    name, score = st.columns([3, 1], vertical_alignment="center")
    with name:
        weight = "**" if side["outcome"] == "won" else ""
        label = f"{weight}{side['team']}{weight}"
        if side["picks"]:
            entries = "entry" if side["picks"] == 1 else "entries"
            label += f" &nbsp;`{side['picks']} {entries}`"
        st.markdown(label)
    with score:
        if status == "pre" or side["score"] is None:
            st.markdown("&nbsp;")
        else:
            weight = "**" if side["outcome"] == "won" else ""
            st.markdown(f"{weight}{side['score']}{weight}")


def _render_card(card: Dict[str, Any]) -> None:
    with st.container(border=True):
        head, line = st.columns([2, 1], vertical_alignment="center")
        with head:
            _status_chip(card)
        with line:
            if card["line"]:
                st.caption(card["line"])

        _team_row(card["away"], card["status"])
        _team_row(card["home"], card["status"])

        # The survivor angle, and the reason this isn't just a scoreboard.
        if card["eliminated"] or card["survived"]:
            if card["eliminated"]:
                st.badge(f"{card['eliminated']} eliminated", icon="💀", color="red")
            if card["survived"]:
                st.badge(f"{card['survived']} survive", icon="✅", color="green")


def render_live_scores_widget(season: int, week: int, reveal_picks: bool) -> None:
    """The week's scoreboard, as a two-column grid of cards.

    Built only from st.container(border=True) and st.badge, whose colours are
    theme tokens. There are deliberately no colour literals in this module, so
    it follows the app's surface wherever that lands.
    """
    data = get_week_scoreboard(season, week)
    cards = build_scoreboard(
        data["games"], data["pick_counts"], data["results"], reveal_picks
    )

    st.markdown(f"### 🏈 Week {week}")

    # Each empty state says WHY it is empty, not merely that it is.
    if not data["games"]:
        st.info(
            f"**No week {week} schedule yet.** Games appear here once the score "
            "ingestion job has pulled this week's fixtures."
        )
        return
    if not cards:
        # Reachable only with picks present and none of the picked teams
        # playing: a bye week, or an abbreviation the sheet and the schedule
        # disagree on. Sending the reader to check the sheet import would point
        # them at the one thing that definitely worked.
        st.info(
            f"**No week {week} game features a picked team.** Every entrant is "
            "on a team that isn't playing this week — usually a bye, or a team "
            "abbreviation the sheet and the schedule spell differently."
        )
        return

    if not reveal_picks:
        st.caption(
            "This week hasn't kicked off — showing the full slate. Pick counts "
            "appear once the games start."
        )
    elif not any(card["has_picks"] for card in cards):
        st.caption("No picks in yet — showing every game this week.")

    for row in range(0, len(cards), 2):
        left, right = st.columns(2, gap="small")
        with left:
            _render_card(cards[row])
        if row + 1 < len(cards):
            with right:
                _render_card(cards[row + 1])
