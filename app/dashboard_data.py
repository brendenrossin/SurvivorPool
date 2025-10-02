"""
Data fetching functions for Streamlit dashboard
"""

import os
import json
import streamlit as st
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text, select
from datetime import datetime

from api.database import SessionLocal
from api.models import Player, Pick, PickResult, Game, JobMeta
from api.config import DEFAULT_LEAGUE_ID

@st.cache_resource
def get_db_session():
    """Get cached database session factory"""
    return SessionLocal

@st.cache_data
def load_team_data() -> Dict:
    """Load team colors and metadata"""
    with open("db/seed_team_map.json", "r") as f:
        return json.load(f)

@st.cache_data(ttl=60)  # 60 second cache - refresh during live windows
def get_summary_data(season: int, league_id: int = DEFAULT_LEAGUE_ID) -> Dict:
    """Get summary data for dashboard"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        # Get weeks with picks
        weeks_query = db.query(Pick.week).filter(
            and_(
                Pick.season == season,
                Pick.league_id == league_id
            )
        ).distinct().all()
        weeks = sorted([w[0] for w in weeks_query])

        # Get total entrants
        total_entrants = db.query(Player).filter(Player.league_id == league_id).count()

        # Get remaining players (no survived=False)
        eliminated_players = db.query(Pick.player_id).join(PickResult).filter(
            and_(
                Pick.season == season,
                Pick.league_id == league_id,
                PickResult.survived == False
            )
        ).distinct().subquery()

        remaining_players = db.query(Player).filter(
            and_(
                Player.league_id == league_id,
                ~Player.player_id.in_(select(eliminated_players.c.player_id))
            )
        ).count()

        # Get picks by week and team
        weeks_data = []
        for week in weeks:
            teams_query = db.query(
                Pick.team_abbr,
                func.count(Pick.pick_id).label('count')
            ).filter(
                and_(
                    Pick.season == season,
                    Pick.league_id == league_id,
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

def get_player_data(player_name: str, season: int, league_id: int = DEFAULT_LEAGUE_ID) -> Optional[Dict]:
    """Get individual player data"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        player = db.query(Player).filter(
            and_(
                Player.display_name == player_name,
                Player.league_id == league_id
            )
        ).first()
        if not player:
            return None

        picks_query = db.query(Pick, PickResult, Game).outerjoin(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).outerjoin(
            Game, PickResult.game_id == Game.game_id
        ).filter(
            and_(
                Pick.player_id == player.player_id,
                Pick.season == season,
                Pick.league_id == league_id
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

        return {
            "player": player_name,
            "season": season,
            "picks": picks
        }

    finally:
        db.close()

@st.cache_data(ttl=60)  # 60 second cache - refresh during live windows
def get_meme_stats(season: int, league_id: int = DEFAULT_LEAGUE_ID) -> Dict:
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
                AND pi.league_id = :league_id
                AND pr.survived = FALSE
                AND g.home_score IS NOT NULL
                AND g.away_score IS NOT NULL
            GROUP BY pi.week, pi.team_abbr, g.home_team, g.away_team, g.home_score, g.away_score
            ORDER BY margin DESC
            LIMIT 5
        """)

        dumbest_results = db.execute(dumbest_query, {"season": season, "league_id": league_id}).fetchall()

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
                AND pi.league_id = :league_id
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

        big_balls_results = db.execute(big_balls_query, {"season": season, "league_id": league_id}).fetchall()

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

@st.cache_data(ttl=300)  # 5 minute cache for player searches
def search_players(query: str, league_id: int = DEFAULT_LEAGUE_ID) -> List[str]:
    """Search for players by name"""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        players = db.query(Player.display_name).filter(
            and_(
                Player.display_name.ilike(f"%{query}%"),
                Player.league_id == league_id
            )
        ).all()

        return [p[0] for p in players]

    finally:
        db.close()

@st.cache_data(ttl=60)  # 60 second cache for league list
def get_all_leagues(season: int) -> List[Dict]:
    """Get all leagues for a given season"""
    from api.models import League

    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        leagues = db.query(League).filter(League.season == season).order_by(League.league_name).all()

        return [{
            "league_id": league.league_id,
            "league_name": league.league_name,
            "league_slug": league.league_slug,
            "pick_source": league.pick_source,
            "commissioner_email": league.commissioner_email
        } for league in leagues]

    finally:
        db.close()

@st.cache_data(ttl=60)  # 60 second cache for league lookup
def get_league_by_slug(league_slug: str, season: int) -> Optional[Dict]:
    """Get league by slug for URL routing"""
    from api.models import League

    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        league = db.query(League).filter(
            and_(
                League.league_slug == league_slug,
                League.season == season
            )
        ).first()

        if not league:
            return None

        return {
            "league_id": league.league_id,
            "league_name": league.league_name,
            "league_slug": league.league_slug,
            "pick_source": league.pick_source,
            "commissioner_email": league.commissioner_email,
            "invite_code": league.invite_code
        }

    finally:
        db.close()