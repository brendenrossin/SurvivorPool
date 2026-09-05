"""
Data fetching functions for Streamlit dashboard
"""

import os
import json
import streamlit as st
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # 3.8+ in stdlib; the Dockerfile pins 3.11
    from typing import TypedDict
except ImportError:  # pragma: no cover
    TypedDict = None
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, select, text
from datetime import datetime

from api.database import SessionLocal
from api.models import Player, Pick, PickResult, Game, JobMeta

@st.cache_resource
def get_db_session():
    """Get cached database session factory"""
    return SessionLocal

@st.cache_data
def load_team_data() -> Dict:
    """Load team colors and metadata"""
    with open("db/seed_team_map.json", "r") as f:
        return json.load(f)

def _season_player_ids(db, season):
    """Subquery of player_ids who made at least one pick in the given season.

    Players are season-independent, so the season lives on picks. Any count
    that starts from the players table must be narrowed through this.
    """
    return db.query(Pick.player_id).filter(Pick.season == season).distinct().subquery()


def count_season_entrants(db, season: int) -> int:
    """Number of players who entered the pool in the given season."""
    return db.query(Pick.player_id).filter(Pick.season == season).distinct().count()


def count_season_survivors(db, season: int) -> int:
    """Number of this season's entrants with no losing pick yet."""
    eliminated = db.query(Pick.player_id).join(PickResult).filter(
        and_(
            Pick.season == season,
            PickResult.survived == False
        )
    ).distinct().subquery()

    return db.query(Player).filter(
        Player.player_id.in_(select(_season_player_ids(db, season).c.player_id)),
        ~Player.player_id.in_(select(eliminated.c.player_id))
    ).count()


def find_season_players(db, season: int, query: str):
    """Player names matching `query` among the given season's entrants."""
    rows = db.query(Player.display_name).filter(
        Player.player_id.in_(select(_season_player_ids(db, season).c.player_id)),
        Player.display_name.ilike(f"%{query}%")
    ).distinct().all()

    return [r[0] for r in rows]


@st.cache_data(ttl=60)
def get_started_game_weeks(season: int) -> List[int]:
    """Weeks with at least one game underway or finished.

    Picks are entered in the sheet weeks ahead of kickoff, so this - not the
    latest week holding a pick - is what tells us which week is live.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(Game.week).filter(
            Game.season == season,
            Game.status != "pre"
        ).distinct().all()
        return sorted(r[0] for r in rows)
    finally:
        try:
            db.close()
        except Exception:
            pass


def count_completed_weeks(week_statuses: Dict[int, List[str]]) -> int:
    """How many weeks have finished, given {week: [game status, ...]}.

    A survival round is over when every game in it is final - not when it has
    picks. The sheet is filled in weeks ahead of kickoff, so counting weeks
    with picks reports a round complete before it has been played.
    """
    return sum(
        1 for statuses in week_statuses.values()
        if statuses and all(status == "final" for status in statuses)
    )


@st.cache_data(ttl=60)
def get_completed_week_count(season: int) -> int:
    """Number of survival rounds actually played out this season."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(Game.week, Game.status).filter(Game.season == season).all()
        by_week: Dict[int, List[str]] = {}
        for week, status in rows:
            by_week.setdefault(week, []).append(status)
        return count_completed_weeks(by_week)
    finally:
        try:
            db.close()
        except Exception:
            pass


@st.cache_data(ttl=60)  # 60 second cache - refresh during live windows
def get_summary_data(season: int) -> Dict:
    """Get summary data for dashboard"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        # Get weeks with picks
        weeks_query = db.query(Pick.week).filter(Pick.season == season).distinct().all()
        weeks = sorted([w[0] for w in weeks_query])

        # Entrants and survivors are scoped to this season's picks so prior
        # seasons' players are not counted.
        total_entrants = count_season_entrants(db, season)
        remaining_players = count_season_survivors(db, season)

        # Get picks by week and team
        weeks_data = []
        for week in weeks:
            teams_query = db.query(
                Pick.team_abbr,
                func.count(Pick.pick_id).label('count')
            ).filter(
                and_(
                    Pick.season == season,
                    Pick.week == week,
                    Pick.team_abbr.isnot(None)
                )
            ).group_by(Pick.team_abbr).all()

            teams = [{"team": team, "count": count} for team, count in teams_query]
            weeks_data.append({"week": week, "teams": teams})

        # Get last update times
        job_meta = db.query(JobMeta).all()
        last_updates = {job.job_name: job.last_success_at for job in job_meta}

        return {
            "season": season,
            "weeks": weeks_data,
            "entrants_total": total_entrants,
            "entrants_remaining": remaining_players,
            "last_updates": last_updates
        }

    finally:
        db.close()

def get_player_data(player_name: str, season: int) -> Optional[Dict]:
    """Get individual player data"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        player = db.query(Player).filter(Player.display_name == player_name).first()
        if not player:
            return None

        picks_query = db.query(Pick, PickResult, Game).outerjoin(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).outerjoin(
            Game, PickResult.game_id == Game.game_id
        ).filter(
            and_(
                Pick.player_id == player.player_id,
                Pick.season == season
            )
        ).order_by(Pick.week).all()

        picks = []
        for pick, pick_result, game in picks_query:
            pick_data = {
                "week": pick.week,
                "team": pick.team_abbr,
                "locked": pick_result.is_locked if pick_result else False,
                "survived": pick_result.survived if pick_result else None,
                "valid": pick_result.is_valid if pick_result else True,
                "game_status": game.status if game else "unknown"
            }
            picks.append(pick_data)

        # Rule: never surface a week that has not kicked off. Without this,
        # "Find a Survivor" publishes the field's upcoming picks.
        picks = clamp_picks_to_week(picks, _last_started_week(season))

        return {
            "player": player_name,
            "season": season,
            "picks": picks
        }

    finally:
        db.close()

@st.cache_data(ttl=60)  # 60 second cache - refresh during live windows
def get_meme_stats(season: int) -> Dict:
    """Get meme statistics for dashboard"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        # Dumbest picks (biggest losing margins) - grouped by team
        dumbest_query = text("""
            SELECT
                pi.week,
                pi.team_abbr,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                CASE
                    WHEN pi.team_abbr = g.home_team THEN g.away_score - g.home_score
                    ELSE g.home_score - g.away_score
                END as margin,
                COUNT(DISTINCT pi.player_id) as eliminated_count
            FROM picks pi
            JOIN pick_results pr ON pi.pick_id = pr.pick_id
            JOIN games g ON (
                (g.home_team = pi.team_abbr OR g.away_team = pi.team_abbr)
                AND g.week = pi.week
                AND g.season = pi.season
            )
            WHERE pi.season = :season
                AND pr.survived = FALSE
                AND g.home_score IS NOT NULL
                AND g.away_score IS NOT NULL
            GROUP BY pi.week, pi.team_abbr, g.home_team, g.away_team, g.home_score, g.away_score
            ORDER BY margin DESC
            LIMIT 5
        """)

        dumbest_results = db.execute(dumbest_query, {"season": season}).fetchall()

        dumbest_picks = []
        for row in dumbest_results:
            opponent = row.away_team if row.team_abbr == row.home_team else row.home_team
            dumbest_picks.append({
                "week": row.week,
                "team": row.team_abbr,
                "opponent": opponent,
                "margin": row.margin,
                "eliminated_count": row.eliminated_count
            })

        # Big balls picks (underdog wins - teams that were underdogs and won) - grouped by team
        big_balls_query = text("""
            SELECT
                pi.week,
                pi.team_abbr,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                g.point_spread,
                g.favorite_team,
                COUNT(DISTINCT pi.player_id) as big_balls_count,
                CASE
                    WHEN g.favorite_team IS NOT NULL AND
                         -- Convert full team names to abbreviations for comparison
                         CASE g.favorite_team
                             WHEN 'Arizona Cardinals' THEN 'ARI'
                             WHEN 'Atlanta Falcons' THEN 'ATL'
                             WHEN 'Baltimore Ravens' THEN 'BAL'
                             WHEN 'Buffalo Bills' THEN 'BUF'
                             WHEN 'Carolina Panthers' THEN 'CAR'
                             WHEN 'Chicago Bears' THEN 'CHI'
                             WHEN 'Cincinnati Bengals' THEN 'CIN'
                             WHEN 'Cleveland Browns' THEN 'CLE'
                             WHEN 'Dallas Cowboys' THEN 'DAL'
                             WHEN 'Denver Broncos' THEN 'DEN'
                             WHEN 'Detroit Lions' THEN 'DET'
                             WHEN 'Green Bay Packers' THEN 'GB'
                             WHEN 'Houston Texans' THEN 'HOU'
                             WHEN 'Indianapolis Colts' THEN 'IND'
                             WHEN 'Jacksonville Jaguars' THEN 'JAX'
                             WHEN 'Kansas City Chiefs' THEN 'KC'
                             WHEN 'Las Vegas Raiders' THEN 'LV'
                             WHEN 'Los Angeles Chargers' THEN 'LAC'
                             WHEN 'Los Angeles Rams' THEN 'LAR'
                             WHEN 'Miami Dolphins' THEN 'MIA'
                             WHEN 'Minnesota Vikings' THEN 'MIN'
                             WHEN 'New England Patriots' THEN 'NE'
                             WHEN 'New Orleans Saints' THEN 'NO'
                             WHEN 'New York Giants' THEN 'NYG'
                             WHEN 'New York Jets' THEN 'NYJ'
                             WHEN 'Philadelphia Eagles' THEN 'PHI'
                             WHEN 'Pittsburgh Steelers' THEN 'PIT'
                             WHEN 'San Francisco 49ers' THEN 'SF'
                             WHEN 'Seattle Seahawks' THEN 'SEA'
                             WHEN 'Tampa Bay Buccaneers' THEN 'TB'
                             WHEN 'Tennessee Titans' THEN 'TEN'
                             WHEN 'Washington Commanders' THEN 'WAS'
                             ELSE g.favorite_team
                         END != pi.team_abbr THEN 1
                    ELSE 0
                END as was_underdog
            FROM picks pi
            JOIN pick_results pr ON pi.pick_id = pr.pick_id
            JOIN games g ON (
                (g.home_team = pi.team_abbr OR g.away_team = pi.team_abbr)
                AND g.week = pi.week
                AND g.season = pi.season
            )
            WHERE pi.season = :season
                AND pr.survived = TRUE
                AND g.home_score IS NOT NULL
                AND g.away_score IS NOT NULL
                AND (
                    -- Original criteria: away team wins (road wins)
                    (pi.team_abbr = g.away_team AND g.away_score > g.home_score)
                    OR
                    -- New criteria: underdog wins (when we have spread data and team actually won)
                    (g.favorite_team IS NOT NULL AND
                     CASE g.favorite_team
                         WHEN 'Arizona Cardinals' THEN 'ARI'
                         WHEN 'Atlanta Falcons' THEN 'ATL'
                         WHEN 'Baltimore Ravens' THEN 'BAL'
                         WHEN 'Buffalo Bills' THEN 'BUF'
                         WHEN 'Carolina Panthers' THEN 'CAR'
                         WHEN 'Chicago Bears' THEN 'CHI'
                         WHEN 'Cincinnati Bengals' THEN 'CIN'
                         WHEN 'Cleveland Browns' THEN 'CLE'
                         WHEN 'Dallas Cowboys' THEN 'DAL'
                         WHEN 'Denver Broncos' THEN 'DEN'
                         WHEN 'Detroit Lions' THEN 'DET'
                         WHEN 'Green Bay Packers' THEN 'GB'
                         WHEN 'Houston Texans' THEN 'HOU'
                         WHEN 'Indianapolis Colts' THEN 'IND'
                         WHEN 'Jacksonville Jaguars' THEN 'JAX'
                         WHEN 'Kansas City Chiefs' THEN 'KC'
                         WHEN 'Las Vegas Raiders' THEN 'LV'
                         WHEN 'Los Angeles Chargers' THEN 'LAC'
                         WHEN 'Los Angeles Rams' THEN 'LAR'
                         WHEN 'Miami Dolphins' THEN 'MIA'
                         WHEN 'Minnesota Vikings' THEN 'MIN'
                         WHEN 'New England Patriots' THEN 'NE'
                         WHEN 'New Orleans Saints' THEN 'NO'
                         WHEN 'New York Giants' THEN 'NYG'
                         WHEN 'New York Jets' THEN 'NYJ'
                         WHEN 'Philadelphia Eagles' THEN 'PHI'
                         WHEN 'Pittsburgh Steelers' THEN 'PIT'
                         WHEN 'San Francisco 49ers' THEN 'SF'
                         WHEN 'Seattle Seahawks' THEN 'SEA'
                         WHEN 'Tampa Bay Buccaneers' THEN 'TB'
                         WHEN 'Tennessee Titans' THEN 'TEN'
                         WHEN 'Washington Commanders' THEN 'WAS'
                         ELSE g.favorite_team
                     END != pi.team_abbr AND pi.team_abbr = g.winner_abbr)
                )
            GROUP BY pi.week, pi.team_abbr, g.home_team, g.away_team, g.home_score, g.away_score, g.point_spread, g.favorite_team
            ORDER BY was_underdog DESC, pi.week DESC
            LIMIT 5
        """)

        big_balls_results = db.execute(big_balls_query, {"season": season}).fetchall()

        big_balls_picks = []
        for row in big_balls_results:
            # Determine if this was a road win
            road_win = row.team_abbr == row.away_team

            # Determine if this was an underdog win
            was_underdog = bool(row.was_underdog)

            # Determine opponent
            opponent = row.home_team if road_win else row.away_team

            big_balls_picks.append({
                "week": row.week,
                "team": row.team_abbr,
                "opponent": opponent,
                "road_win": road_win,
                "was_underdog": was_underdog,
                "point_spread": row.point_spread,
                "favorite_team": row.favorite_team,
                "big_balls_count": row.big_balls_count
            })

        return {
            "dumbest_picks": dumbest_picks,
            "big_balls_picks": big_balls_picks
        }

    finally:
        db.close()

# --- Attrition, doom and the graveyard -------------------------------------
#
# Every widget's database access lives here. The render_* functions are pure
# view code, so nothing in app/ opens a session on a script run except this
# module - and everything here is cached.


def build_attrition_rows(entrants, elims_by_week, weeks):
    """Turn {week: first-eliminations} into the field's week-by-week decline.

    Pure, so the arithmetic is testable without a database. `entering` is the
    field at the start of the week; `remaining` is what survived it.
    """
    rows = []
    alive = entrants
    for week in sorted(weeks):
        out = elims_by_week.get(week, 0)
        entering = alive
        alive = entering - out
        rows.append({
            "week": week,
            "entering": entering,
            "eliminated": out,
            "remaining": alive,
            "pct_out": round(out / entering * 100, 1) if entering > 0 else 0.0,
        })
    return rows


def select_attrition_weeks(pick_weeks, last_started_week):
    """Which weeks belong in the attrition series.

    Only weeks that have kicked off. The sheet holds picks for unplayed weeks,
    so without this a pre-season week 1 reports "5 entered, 0 eliminated" as
    though it had been played. Before any kickoff the series is empty and the
    caller shows its own empty state.
    """
    if last_started_week is None:
        return []
    return [w for w in sorted(pick_weeks) if w <= last_started_week]


def _first_elimination_subquery(db, season):
    """Each player's first losing week - the graveyard's definition.

    A player who keeps filling in the sheet after going out has later losing
    picks too; attributing them all would count one elimination many times.
    """
    return db.query(
        Pick.player_id,
        func.min(Pick.week).label("week"),
    ).join(
        PickResult, Pick.pick_id == PickResult.pick_id
    ).filter(
        Pick.season == season,
        PickResult.survived == False,  # noqa: E712
    ).group_by(Pick.player_id).subquery()


def _last_started_week(season):
    """The last week that has kicked off, or None before the season starts."""
    started = get_started_game_weeks(season)
    return max(started) if started else None


@st.cache_data(ttl=60)
def get_attrition_series(season: int):
    """The field's week-by-week decline, in one query.

    Replaces a three-queries-per-week loop - 42 round trips for 2025's 14
    weeks - and is the shared spine behind the KPI sparkline, the elimination
    tracker and the survivors board.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        entrants = count_season_entrants(db, season)

        first = _first_elimination_subquery(db, season)
        elims = {
            week: n for week, n in db.query(
                first.c.week, func.count().label("n")
            ).group_by(first.c.week).all()
        }

        weeks = sorted(
            w[0] for w in
            db.query(Pick.week).filter(Pick.season == season).distinct().all()
        )

        weeks = select_attrition_weeks(weeks, _last_started_week(season))
        return build_attrition_rows(entrants, elims, weeks)
    finally:
        try:
            db.close()
        except Exception:
            pass


def rank_doom_teams(rows):
    """Order (team, eliminations, first_week) triples for display.

    `first_week` is the earliest week this team ended anyone's run - not the
    team's worst week. TB's is 14 because that is when it first eliminated
    someone, which is a different fact from where it did the most damage.

    Null-team rows are dropped: a missed pick eliminates a player but is not a
    team, and 2025 has 233 of them - they would top the ranking and mean
    nothing. Ties break alphabetically so the order is stable between runs.
    """
    cleaned = [r for r in rows if r[0]]
    cleaned.sort(key=lambda r: (-r[1], r[0]))
    return [
        {"team": team, "eliminations": n, "first_week": worst}
        for team, n, worst in cleaned
    ]


@st.cache_data(ttl=60)
def get_doom_teams(season: int):
    """Teams ranked by how many entrants they eliminated.

    First-elimination attributed, matching the graveyard. Counting every
    losing pick answers a different question - how often a team lost while
    someone had it - which is not what "team of doom" means.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        first = _first_elimination_subquery(db, season)
        rows = db.query(
            Pick.team_abbr,
            func.count(func.distinct(Pick.player_id)).label("n"),
            func.min(Pick.week).label("first_week"),
        ).join(
            first,
            and_(Pick.player_id == first.c.player_id,
                 Pick.week == first.c.week),
        ).filter(
            Pick.season == season
        ).group_by(Pick.team_abbr).all()
        return rank_doom_teams([(t, n, w) for t, n, w in rows])
    finally:
        try:
            db.close()
        except Exception:
            pass


@st.cache_data(ttl=60)
def get_graveyard(season: int):
    """Eliminated entrants and the pick that ended them, one row per player."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        first = _first_elimination_subquery(db, season)
        rows = db.query(
            Player.display_name, Pick.week, Pick.team_abbr,
            Game.home_team, Game.away_team, Game.home_score, Game.away_score,
        ).join(
            Pick, Player.player_id == Pick.player_id
        ).join(
            first,
            and_(Pick.player_id == first.c.player_id,
                 Pick.week == first.c.week),
        ).outerjoin(
            Game,
            and_(
                or_(Game.home_team == Pick.team_abbr,
                    Game.away_team == Pick.team_abbr),
                Game.week == Pick.week,
                Game.season == season,
            ),
        ).filter(
            Pick.season == season
        ).order_by(Pick.week, Player.display_name).all()

        out = []
        for name, week, team, home, away, home_score, away_score in rows:
            if team is None:
                out.append({
                    "player": name, "week": week, "team": None,
                    "opponent": None, "location": "", "margin": None,
                    "final_score": None, "game_summary": "No pick submitted",
                })
                continue

            if home == team:
                opponent, location = away, "vs"
                theirs, others = home_score, away_score
            else:
                opponent, location = home, "at"
                theirs, others = away_score, home_score

            scored = theirs is not None and others is not None
            out.append({
                "player": name, "week": week, "team": team,
                "opponent": opponent, "location": location,
                "margin": (others - theirs) if scored else None,
                "final_score": f"{theirs}-{others}" if scored else None,
                "game_summary": f"{team} {location} {opponent}"
                                if opponent else team,
            })
        return out
    finally:
        try:
            db.close()
        except Exception:
            pass


@st.cache_data(ttl=60)
def get_survivor_board(season: int):
    """Every still-alive entrant with their pick history, in one query.

    Replaces a loop of 2N + 2 round trips. It also starts from this season's
    picks rather than the players table, which is season-independent - a query
    that starts from Player counts everyone who ever entered the pool.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        eliminated = db.query(Pick.player_id).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == season,
            PickResult.survived == False,  # noqa: E712
        ).distinct().subquery()

        query = db.query(
            Player.display_name, Pick.week, Pick.team_abbr,
        ).join(
            Pick, Player.player_id == Pick.player_id
        ).filter(
            Pick.season == season,
            ~Player.player_id.in_(select(eliminated.c.player_id)),
        )

        cutoff = _last_started_week(season)
        if cutoff is not None:
            query = query.filter(Pick.week <= cutoff)

        board = {}
        for name, week, team in query.order_by(Player.display_name, Pick.week).all():
            entry = board.setdefault(name, {
                "player": name, "picks": 0, "teams_used": [],
                "latest_week": 0, "latest_team": None,
            })
            entry["picks"] += 1
            if team:
                entry["teams_used"].append(team)
            if week >= entry["latest_week"]:
                entry["latest_week"], entry["latest_team"] = week, team
        return list(board.values())
    finally:
        try:
            db.close()
        except Exception:
            pass


def clamp_picks_to_week(picks, current_week):
    """Drop picks for weeks that have not kicked off.

    The sheet holds future weeks' picks from day one, so returning them
    publishes the field's upcoming picks - the leak the picks grid exists to
    prevent. `None` means no clamp is known and the caller gets everything.
    """
    if current_week is None:
        return picks
    return [p for p in picks if p["week"] <= current_week]


@st.cache_data(ttl=300)  # 5 minute cache for player searches
def search_players(query: str, season: int) -> List[str]:
    """Search this season's players by name"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        return find_season_players(db, season, query)

    finally:
        db.close()

def decide_week_results(
    games: Iterable[Tuple[str, str, str, Optional[int], Optional[int]]],
) -> Dict[str, str]:
    """{team: 'won' | 'lost' | 'pending'} for one week's games.

    Rows are (status, home_team, away_team, home_score, away_score).

    A TIE IS A LOSS FOR BOTH TEAMS. Survivor pools pay out on a win, so a tie
    eliminates everyone who picked either side. Anything that is not a final
    game with both scores present is 'pending' - including a live game, where a
    team leading at half has survived nothing yet, and a game marked final
    before ingestion has filled the score in.

    This rule used to live inline in a Streamlit render function, where no test
    could reach it: deleting it passed the entire suite.
    """
    status: Dict[str, str] = {}
    for game_status, home, away, home_score, away_score in games:
        decided = (
            game_status == "final"
            and home_score is not None
            and away_score is not None
        )
        if not decided:
            status.setdefault(home, "pending")
            status.setdefault(away, "pending")
        elif home_score == away_score:
            status[home] = status[away] = "lost"
        elif home_score > away_score:
            status[home], status[away] = "won", "lost"
        else:
            status[away], status[home] = "won", "lost"
    return status


@st.cache_data(ttl=60)
def get_week_team_status(season: int, week: int) -> Dict[str, str]:
    """Cached {team: 'won' | 'lost' | 'pending'} for one week.

    Replaces an uncached whole-ORM-row Game query that ran inline in the render
    path on every script rerun - which the grid's two controls now trigger on
    every toggle.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(
            Game.status, Game.home_team, Game.away_team,
            Game.home_score, Game.away_score,
        ).filter(Game.season == season, Game.week == week).all()
        return decide_week_results(rows)
    finally:
        try:
            db.close()
        except Exception:
            pass


@st.cache_data(ttl=60)
def get_week_game_statuses(season: int) -> Dict[int, List[str]]:
    """{week: [game status, ...]} for a whole season."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(Game.week, Game.status).filter(Game.season == season).all()
        by_week: Dict[int, List[str]] = {}
        for week, status in rows:
            by_week.setdefault(week, []).append(status)
        return by_week
    finally:
        try:
            db.close()
        except Exception:
            pass


class Scoreboard(TypedDict):
    """One week's scoreboard payload.

    `games` rows carry the ten Game columns build_scoreboard reads;
    `pick_counts` is {team: picks}; `results` is {game_id: {"survived": n,
    "eliminated": n}}.
    """

    games: List[Dict[str, Any]]
    pick_counts: Dict[str, int]
    results: Dict[str, Dict[str, int]]


@st.cache_data(ttl=60)
def get_week_scoreboard(season: int, week: int) -> Scoreboard:
    """Games, pick counts and survival splits for one week, as plain dicts.

    Returns plain data rather than ORM rows so the view layer stays free of the
    session, and so the whole payload is cacheable.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        # Columns, not whole ORM rows: every one of these is projected straight
        # into a dict on the next line, so hydrating Game instances and an
        # identity map buys nothing. No order_by either - build_scoreboard
        # sorts unconditionally.
        games = [{
            "game_id": game_id, "status": status,
            "home_team": home_team, "away_team": away_team,
            "home_score": home_score, "away_score": away_score,
            "winner_abbr": winner_abbr, "kickoff": kickoff,
            "favorite_team": favorite_team, "point_spread": point_spread,
        } for (game_id, status, home_team, away_team, home_score, away_score,
               winner_abbr, kickoff, favorite_team, point_spread) in db.query(
            Game.game_id, Game.status, Game.home_team, Game.away_team,
            Game.home_score, Game.away_score, Game.winner_abbr, Game.kickoff,
            Game.favorite_team, Game.point_spread,
        ).filter(Game.season == season, Game.week == week).all()]

        counts = dict(db.query(Pick.team_abbr, func.count()).filter(
            Pick.season == season, Pick.week == week,
            Pick.team_abbr.isnot(None),
        ).group_by(Pick.team_abbr).all())

        results: Dict[str, Dict[str, int]] = {}
        rows = db.query(PickResult.game_id, PickResult.survived, func.count()).join(
            Pick, Pick.pick_id == PickResult.pick_id
        ).filter(Pick.season == season, Pick.week == week).group_by(
            PickResult.game_id, PickResult.survived
        ).all()
        for game_id, survived, count in rows:
            split = results.setdefault(game_id, {"survived": 0, "eliminated": 0})
            if survived is True:
                split["survived"] += count
            elif survived is False:
                split["eliminated"] += count

        return {"games": games, "pick_counts": counts, "results": results}
    finally:
        try:
            db.close()
        except Exception:
            pass
