#!/usr/bin/env python3
"""Live scores — the week's games as a grid of cards.

What separates this from any scoreboard is the second line of every card: how
many entrants are riding on each team, and what just happened to them. That is
the reason anyone opens this page instead of ESPN's.

Data comes from the database only. API calls happen in the cron jobs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import html

import pytz
import streamlit as st

from app.dashboard_data import get_week_scoreboard, load_team_data
from app.theme import INK_MUTED, SURFACE, contrast_fill
from app.odds_helpers import format_pregame_line

CARDS_PER_ROW = 4

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


# This pool's picks are already public before kickoff by its own process:
# entrants post them to a GroupMe where everyone sees them, and the manager
# aggregates them into the sheet afterwards. So the scoreboard has nothing left
# to disclose and may filter and count before a week starts.
# See docs/pool-process.md.
#
# The gate below is kept rather than deleted: set this False for a pool that
# collects picks privately, and the pre-kickoff protections come back intact.
PICKS_ARE_PUBLIC = True


def should_reveal_picks(
    scoreboard_week: int,
    started_weeks: Iterable[int],
    picks_are_public: bool = PICKS_ARE_PUBLIC,
) -> bool:
    """Whether the scoreboard may show pick data for `scoreboard_week`.

    Returns True unconditionally when the pool's picks are public anyway - see
    PICKS_ARE_PUBLIC. The rest of this docstring describes the private-pool
    case, which is what the gate protects when that flag is off.

    A week reveals its picks if and only if one of its OWN games has left
    'pre'. Stated that way the invariant is local and unconditional, which is
    the point: the first version derived it by comparing the scoreboard's week
    against the grid's, and that ordering is satisfied in exactly the case it
    most needed to exclude. Before any game of the season has started,
    resolve_current_week falls back to the first week holding picks rather than
    reporting "nothing has started", so both weeks were 1 and 1 <= 1 published
    the entire field's week 1 picks days before kickoff.
    """
    if picks_are_public:
        return True
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


def _status_html(card: Dict[str, Any]) -> str:
    """Kickoff time, or the game's state once it has one."""
    if card["status"] == "in":
        return '<span class="sb-live"><span class="sb-pulse"></span>LIVE</span>'
    if card["status"] == "final":
        return '<span class="sb-when">FINAL</span>'
    if card["kickoff"]:
        local = _as_utc(card["kickoff"]).astimezone(PACIFIC)
        return f'<span class="sb-when">{local.strftime("%a %-I:%M %p")}</span>'
    return '<span class="sb-when">TBD</span>'


def _team_html(side: Dict[str, Any], status: str, color: str) -> str:
    """One team's line: colour bar, abbreviation, pick count, score.

    The count sits in a pill next to the name rather than as text, so it never
    reads as part of the score at the other end of the row. Both teams get one
    when both were picked - rare, but it happened twice in 2025.
    """
    team = html.escape(side["team"])
    state = f" {side['outcome']}" if side["outcome"] else ""

    picks = ""
    if side["picks"]:
        entries = "entry" if side["picks"] == 1 else "entries"
        picks = (f'<span class="sb-picks" title="{side["picks"]} {entries}">'
                 f'{side["picks"]}</span>')

    score = ""
    if status != "pre" and side["score"] is not None:
        score = f'<span class="sb-score{state}">{side["score"]}</span>'

    return (
        f'<div class="sb-row">'
        f'<span class="sb-bar" style="background:{color}"></span>'
        f'<span class="sb-team{state}">{team}</span>'
        f'{picks}<span class="sb-gap"></span>{score}'
        f'</div>'
    )


def _card_html(card: Dict[str, Any], colors: Dict[str, str]) -> str:
    """A whole card as one block.

    One markdown call rather than nested st.columns: the cards sit four to a
    row now, and each Streamlit block added vertical padding the card could not
    spare.
    """
    line = (f'<span class="sb-line">{html.escape(card["line"])}</span>'
            if card["line"] else "")

    foot = []
    if card["eliminated"]:
        foot.append(f'<span class="sb-out">{card["eliminated"]} out</span>')
    if card["survived"]:
        foot.append(f'<span class="sb-through">{card["survived"]} through</span>')
    footer = (f'<div class="sb-foot">{" ".join(foot)}</div>') if foot else ""

    return (
        f'<div class="sb-card">'
        f'<div class="sb-meta">{_status_html(card)}{line}</div>'
        f'{_team_html(card["away"], card["status"], _dot(card["away"]["team"], colors))}'
        f'{_team_html(card["home"], card["status"], _dot(card["home"]["team"], colors))}'
        f'{footer}'
        f'</div>'
    )


def _dot(team: str, colors: Dict[str, str]) -> str:
    """A team's colour, lifted to clear the surface.

    The bar is a small mark floating on the surface with no border, so it is
    the contrast_fill case: GB #203731 is 1.47:1 on the dark surface untreated.
    """
    return contrast_fill(colors.get(team, INK_MUTED), SURFACE)


def _render_card(card: Dict[str, Any], colors: Dict[str, str]) -> None:
    st.markdown(_card_html(card, colors), unsafe_allow_html=True)


def render_live_scores_widget(season: int, week: int, reveal_picks: bool) -> None:
    """The week's scoreboard, as a grid of cards.

    Cards are one markdown block each, styled by the .sb-* rules in
    app/theme.py. Every colour comes from a theme token or from a team colour
    passed through contrast_fill - there are no colour literals in this module,
    so it follows the app's surface wherever that lands.
    """
    data = get_week_scoreboard(season, week)
    cards = build_scoreboard(
        data["games"], data["pick_counts"], data["results"], reveal_picks
    )

    # Each empty state says WHY it is empty, not merely that it is. These sit
    # outside the expander: an expander labelled "0 games" hiding the reason is
    # worse than the reason itself.
    if not data["games"]:
        st.markdown(f"### Week {week}")
        st.info(
            f"**No week {week} schedule yet.** Games appear here once the score "
            "ingestion job has pulled this week's fixtures."
        )
        return
    if not cards:
        st.markdown(f"### Week {week}")
        st.info(
            f"**No week {week} game features a picked team.** Every entrant is "
            "on a team that isn't playing this week — usually a bye, or a team "
            "abbreviation the sheet and the schedule spell differently."
        )
        return

    # Collapsible: a full slate is sixteen cards, which is most of a phone
    # screen before anything else on the page. The count is in the label so the
    # collapsed state still says what is in there.
    # Open once the week is under way, collapsed before it. An upcoming slate
    # is reference material you scroll past; a live one is the reason the page
    # is open.
    week_started = any(game["status"] != "pre" for game in data["games"])
    colors = {team: entry.get("color", INK_MUTED)
              for team, entry in load_team_data()["teams"].items()}
    plural = "game" if len(cards) == 1 else "games"
    with st.expander(f"Week {week} scoreboard - {len(cards)} {plural}",
                     expanded=week_started):
        if not week_started:
            st.caption("This week hasn't kicked off yet.")
        elif not any(card["has_picks"] for card in cards):
            st.caption("No picks in yet - showing every game this week.")

        for start in range(0, len(cards), CARDS_PER_ROW):
            columns = st.columns(CARDS_PER_ROW, gap="small")
            for column, card in zip(columns, cards[start:start + CARDS_PER_ROW]):
                with column:
                    _render_card(card, colors)
