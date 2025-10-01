#!/usr/bin/env python3
"""
Backfill historical weeks 1 and 2 with game results for elimination detection
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.database import SessionLocal
from api.models import Game, Pick, PickResult
from api.score_providers import ESPNScoreProvider
from dotenv import load_dotenv
from sqlalchemy import and_

def backfill_week(week_num):
    """Backfill a specific week with historical data"""
    print(f"🔄 Backfilling Week {week_num}...")

    db = SessionLocal()
    try:
        # Get games for this week
        score_provider = ESPNScoreProvider()
        season = int(os.getenv('NFL_SEASON', 2025))
        games = score_provider.get_schedule_and_scores(season, week_num)

        print(f"📥 Fetched {len(games)} games for Week {week_num}")

        # Save games to database
        games_added = 0
        for game_data in games:
            # Check if game already exists
            existing = db.query(Game).filter(Game.game_id == game_data.game_id).first()
            if not existing:
                # Create new SQLAlchemy Game model from dataclass
                new_game = Game(
                    game_id=game_data.game_id,
                    season=game_data.season,
                    week=game_data.week,
                    kickoff=game_data.kickoff,
                    home_team=game_data.home_team,
                    away_team=game_data.away_team,
                    status=game_data.status,
                    home_score=game_data.home_score,
                    away_score=game_data.away_score,
                    winner_abbr=game_data.winner_abbr
                )
                db.add(new_game)
                games_added += 1
            else:
                # Update existing game with latest info
                existing.status = game_data.status
                existing.home_score = game_data.home_score
                existing.away_score = game_data.away_score
                existing.winner_abbr = game_data.winner_abbr

        db.commit()
        print(f"✅ Added/updated {games_added} games for Week {week_num}")

        # Create pick results for this week
        picks = db.query(Pick).filter(and_(Pick.season == season, Pick.week == week_num)).all()
        results_created = 0

        for pick in picks:
            # Check if pick result already exists
            existing_result = db.query(PickResult).filter(PickResult.pick_id == pick.pick_id).first()
            if existing_result:
                continue

            # Find the game for this pick
            game_data = None
            for g in games:
                if pick.team_abbr in [g.home_team, g.away_team]:
                    game_data = g
                    break

            if game_data:
                # Create pick result
                survived = None
                if game_data.status == "final" and game_data.winner_abbr:
                    survived = (pick.team_abbr == game_data.winner_abbr)

                result = PickResult(
                    pick_id=pick.pick_id,
                    game_id=game_data.game_id,
                    is_valid=True,
                    is_locked=True,  # Historical weeks are locked
                    survived=survived
                )
                db.add(result)
                results_created += 1

        db.commit()
        print(f"✅ Created {results_created} pick results for Week {week_num}")

        # Show elimination summary
        if results_created > 0:
            eliminated = db.query(PickResult).join(Pick).filter(
                and_(Pick.season == season, Pick.week == week_num, PickResult.survived == False)
            ).count()
            survived = db.query(PickResult).join(Pick).filter(
                and_(Pick.season == season, Pick.week == week_num, PickResult.survived == True)
            ).count()
            print(f"📊 Week {week_num} results: {survived} survived, {eliminated} eliminated")

    except Exception as e:
        print(f"❌ Error backfilling Week {week_num}: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

def main():
    """Backfill historical weeks"""
    print("🔄 Backfilling Historical NFL Weeks for Elimination Detection")
    print("=" * 60)

    load_dotenv()

    # Backfill weeks 1 and 2
    for week in [1, 2]:
        backfill_week(week)
        print()

    print("🎉 Historical backfill complete!")

if __name__ == "__main__":
    main()