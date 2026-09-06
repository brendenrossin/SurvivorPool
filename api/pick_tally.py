"""Count this week's picks out of the GroupMe, before the sheet has them.

Three rules bound the count, and the number the widget leads with is wrong if
any of them is missing:

1. **A week window.** Declarations belong to the week they were made in. The
   prototype had no lower bound, so "last declaration wins" ran across the
   whole season and every prior week's pick stayed live - it reported 239 picks
   for week 14 of 2025 against a sheet of 19.
2. **Sender uniqueness.** Keyed on GroupMe's user_id, last declaration wins, so
   an entrant who switches is counted once. Mapping a sender to a sheet entrant
   is deliberately NOT done here; the manager does that himself.
3. **A per-team cutoff.** An entrant may switch until the team they picked
   plays, so a declaration counts only if it was made before that team's own
   kickoff - not the week's last, which would let "switching to DEN" land after
   Denver had already played.

See docs/design/groupme-recap-spec.md, "The unconfirmed pick tally".
"""

import collections
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func

from api.models import ChatMessage, Game
from api.pick_parser import parse_team

# Week 1 has no previous week to start from, and an unbounded start is not a
# safe default: this GroupMe is reused season to season, so it would pull last
# season's declarations into this season's opening tally. Three weeks covers
# the pre-season chatter where week 1 picks actually get posted - measured
# against 2025 week 1, where it captures the same declarations an unbounded
# window does.
WEEK_ONE_LOOKBACK = timedelta(days=21)


def resolve_window(db, season: int,
                   week: int) -> Optional[tuple[datetime, datetime]]:
    """The interval a week's declarations must fall in, or None if unknown.

    Returns (start, end). Both come from the games table, so both carry the
    database's own timezone awareness - naive on SQLite, aware on Postgres.
    Nothing here compares them against a Python-generated `now`, which is what
    would make that difference bite.
    """
    end = (db.query(func.max(Game.kickoff))
             .filter(Game.season == season, Game.week == week).scalar())
    if end is None:
        return None

    previous = (db.query(func.max(Game.kickoff))
                  .filter(Game.season == season, Game.week == week - 1)
                  .scalar())
    if previous is not None:
        return previous, end

    first = (db.query(func.min(Game.kickoff))
               .filter(Game.season == season, Game.week == week).scalar())
    return first - WEEK_ONE_LOOKBACK, end


def team_kickoffs(db, season: int, week: int) -> dict[str, datetime]:
    """Each team's kickoff that week, by abbreviation.

    Doubles as the set of teams it is possible to pick: a team on a bye has no
    entry, so declaring it is talk rather than a pick.
    """
    kickoffs: dict[str, datetime] = {}
    for home, away, kickoff in (db.query(Game.home_team, Game.away_team,
                                         Game.kickoff)
                                  .filter(Game.season == season,
                                          Game.week == week).all()):
        for team in (home, away):
            if team and (team not in kickoffs or kickoff < kickoffs[team]):
                kickoffs[team] = kickoff
    return kickoffs


def tally_unconfirmed(db, season: int, week: int) -> collections.Counter:
    """Picks per team parsed out of the week's chat, one per sender.

    The count is expected to undershoot the sheet - roughly three quarters of
    it, measured across 2025 - because only unambiguous declarations parse.
    That is the safe direction for a number shown as unconfirmed.
    """
    window = resolve_window(db, season, week)
    if window is None:
        return collections.Counter()
    start, end = window

    kickoffs = team_kickoffs(db, season, week)
    if not kickoffs:
        return collections.Counter()

    rows = (db.query(ChatMessage)
              .filter(ChatMessage.is_system.is_(False))
              .filter(ChatMessage.sender_type != "bot")
              .filter(ChatMessage.created_at >= start)
              .filter(ChatMessage.created_at < end)
              .order_by(ChatMessage.created_at)
              .all())

    per_sender: dict[str, str] = {}
    for row in rows:
        team = parse_team(row.text)
        if team is None:
            continue
        kickoff = kickoffs.get(team)
        # A team not playing cannot be picked, and a team already playing can
        # no longer be switched to. Either way the declaration is not a pick,
        # and must not displace an earlier valid one for the same sender.
        if kickoff is None or row.created_at >= kickoff:
            continue
        per_sender[row.sender_id] = team

    return collections.Counter(per_sender.values())


def resolve_pick_week(db, season: int) -> Optional[int]:
    """The week the tally is about: the first one not yet fully played.

    Deliberately not the same question app/picks_grid.resolve_current_week
    answers. The grid leads with the last week that kicked off, because that is
    the last week whose picks are public. The tally is about the week people
    can still declare for, which is the next one whenever the current week has
    finished.

    Resolved from game status, not from a clock. That matches how
    app/dashboard_data.get_started_game_weeks already decides what is live, and
    it avoids comparing a Python `now` against a kickoff column - naive on
    SQLite, aware on Postgres, TypeError where they meet.
    """
    unplayed = (db.query(func.min(Game.week))
                  .filter(Game.season == season, Game.status == "pre")
                  .scalar())
    if unplayed is not None:
        return unplayed
    # Season over, or every game already settled: stay on the last real week
    # rather than reporting nothing.
    return (db.query(func.max(Game.week))
              .filter(Game.season == season).scalar())
