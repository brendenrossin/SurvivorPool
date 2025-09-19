"""
Data fetching functions for Streamlit dashboard
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text, select
from datetime import datetime

from api.database import SessionLocal
from api.models import Player, Pick, PickResult, Game, JobMeta

def load_team_data() -> Dict:
    """Load team colors and metadata"""
    with open("db/seed_team_map.json", "r") as f:
        return json.load(f)

def get_summary_data(season: int) -> Dict:
    """Get summary data for dashboard"""
    db = SessionLocal()
    try:
        # Get weeks with picks
        weeks_query = db.query(Pick.week).filter(Pick.season == season).distinct().all()
        weeks = sorted([w[0] for w in weeks_query])

        # Get total entrants
        total_entrants = db.query(Player).count()

        # Get remaining players (no survived=False)
        eliminated_players = db.query(Pick.player_id).join(PickResult).filter(
            and_(
                Pick.season == season,
                PickResult.survived == False
            )
        ).distinct().subquery()

        remaining_players = db.query(Player).filter(
            ~Player.player_id.in_(select(eliminated_players.c.player_id))
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
    db = SessionLocal()
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

        return {
            "player": player_name,
            "season": season,
            "picks": picks
        }

    finally:
        db.close()

def get_meme_stats(season: int) -> Dict:
    """Get meme statistics for dashboard"""
    db = SessionLocal()
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

        # Big balls picks (underdog wins - road team beating home team for now) - grouped by team
        big_balls_query = text("""
            SELECT
                pi.week,
                pi.team_abbr,
                g.home_team,
                g.away_team,
                g.home_score,
                g.away_score,
                COUNT(DISTINCT pi.player_id) as big_balls_count
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
                AND pi.team_abbr = g.away_team  -- picked away team
                AND g.away_score > g.home_score  -- away team won
            GROUP BY pi.week, pi.team_abbr, g.home_team, g.away_team, g.home_score, g.away_score
            ORDER BY pi.week DESC
            LIMIT 5
        """)

        big_balls_results = db.execute(big_balls_query, {"season": season}).fetchall()

        big_balls_picks = []
        for row in big_balls_results:
            big_balls_picks.append({
                "week": row.week,
                "team": row.team_abbr,
                "opponent": row.home_team,
                "road_win": True,
                "big_balls_count": row.big_balls_count
            })

        return {
            "dumbest_picks": dumbest_picks,
            "big_balls_picks": big_balls_picks
        }

    finally:
        db.close()

def search_players(query: str) -> List[str]:
    """Search for players by name"""
    db = SessionLocal()
    try:
        players = db.query(Player.display_name).filter(
            Player.display_name.ilike(f"%{query}%")
        ).all()

        return [p[0] for p in players]

    finally:
        db.close()