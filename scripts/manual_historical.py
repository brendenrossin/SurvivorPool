#!/usr/bin/env python3
"""
Manually create historical pick results based on known elimination data
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.database import SessionLocal
from api.models import Player, Pick, PickResult, Game
from dotenv import load_dotenv
from sqlalchemy import and_

def mark_eliminations():
    """Mark known eliminations manually"""
    print("🔄 Manually marking known eliminations...")

    load_dotenv()
    db = SessionLocal()

    try:
        season = int(os.getenv('NFL_SEASON', 2025))

        # Known eliminations from user data
        week1_eliminated = ['Andrew Lee', 'Conor Chesterman', 'Grodo', 'Mike Iloski', 'Seth Grom', 'Trevor Franklin']
        week2_eliminated = ['Brian Iloski', 'Eric Iloski', 'James Acres', 'Klayton Wood', 'Kyle Wills', 'Ryan Rock', 'Tanner Caldwell', 'Tommy Kherkher']

        results_created = 0

        # Process Week 1 eliminations
        for name in week1_eliminated:
            player = db.query(Player).filter(Player.display_name == name).first()
            if player:
                pick = db.query(Pick).filter(and_(Pick.player_id == player.player_id, Pick.season == season, Pick.week == 1)).first()
                if pick:
                    # Check if result already exists
                    existing = db.query(PickResult).filter(PickResult.pick_id == pick.pick_id).first()
                    if not existing:
                        result = PickResult(
                            pick_id=pick.pick_id,
                            game_id=None,  # We'll link this later
                            is_valid=True,
                            is_locked=True,
                            survived=False  # Eliminated
                        )
                        db.add(result)
                        results_created += 1
                        print(f"  ❌ {name}: Week 1 pick {pick.team_abbr} -> ELIMINATED")

        # Process Week 2 eliminations
        for name in week2_eliminated:
            player = db.query(Player).filter(Player.display_name == name).first()
            if player:
                pick = db.query(Pick).filter(and_(Pick.player_id == player.player_id, Pick.season == season, Pick.week == 2)).first()
                if pick:
                    # Check if result already exists
                    existing = db.query(PickResult).filter(PickResult.pick_id == pick.pick_id).first()
                    if not existing:
                        result = PickResult(
                            pick_id=pick.pick_id,
                            game_id=None,  # We'll link this later
                            is_valid=True,
                            is_locked=True,
                            survived=False  # Eliminated
                        )
                        db.add(result)
                        results_created += 1
                        print(f"  ❌ {name}: Week 2 pick {pick.team_abbr} -> ELIMINATED")

        # Mark survivors for completed weeks
        # Week 1 survivors (everyone who wasn't eliminated)
        week1_picks = db.query(Pick).filter(and_(Pick.season == season, Pick.week == 1)).all()
        for pick in week1_picks:
            player = db.query(Player).filter(Player.player_id == pick.player_id).first()
            if player and player.display_name not in week1_eliminated:
                existing = db.query(PickResult).filter(PickResult.pick_id == pick.pick_id).first()
                if not existing:
                    result = PickResult(
                        pick_id=pick.pick_id,
                        game_id=None,
                        is_valid=True,
                        is_locked=True,
                        survived=True  # Survived
                    )
                    db.add(result)
                    results_created += 1

        # Week 2 survivors (week 1 survivors who weren't eliminated in week 2)
        week2_picks = db.query(Pick).filter(and_(Pick.season == season, Pick.week == 2)).all()
        for pick in week2_picks:
            player = db.query(Player).filter(Player.player_id == pick.player_id).first()
            if player and player.display_name not in week1_eliminated and player.display_name not in week2_eliminated:
                existing = db.query(PickResult).filter(PickResult.pick_id == pick.pick_id).first()
                if not existing:
                    result = PickResult(
                        pick_id=pick.pick_id,
                        game_id=None,
                        is_valid=True,
                        is_locked=True,
                        survived=True  # Survived
                    )
                    db.add(result)
                    results_created += 1

        db.commit()
        print(f"✅ Created {results_created} pick results")

        # Summary
        total_eliminated = db.query(PickResult).filter(PickResult.survived == False).count()
        total_survived = db.query(PickResult).filter(PickResult.survived == True).count()
        total_pending = db.query(PickResult).filter(PickResult.survived == None).count()

        print(f"📊 Final status:")
        print(f"   Eliminated: {total_eliminated}")
        print(f"   Survived: {total_survived}")
        print(f"   Pending: {total_pending}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    mark_eliminations()