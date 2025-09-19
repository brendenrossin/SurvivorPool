#!/usr/bin/env python3
"""
NFL-only data population script for Railway
Use this until Google Sheets access is configured
"""

import sys
import os

def main():
    print("🏈 Populating SurvivorPool Database (NFL Games Only)...")
    print("=" * 50)

    # Step 1: Get NFL scores and games
    print("\n🏈 Step 1: Fetching NFL scores...")
    try:
        from jobs.update_scores import ScoreUpdater
        updater = ScoreUpdater()
        result = updater.run()
        if result:
            print("✅ NFL scores updated successfully!")
        else:
            print("⚠️ NFL scores update completed with warnings")
    except Exception as e:
        print(f"❌ NFL scores update failed: {e}")
        return False

    # Step 2: Create comprehensive mock survivor data
    print("\n🎭 Step 2: Creating comprehensive mock survivor data...")
    try:
        from api.database import SessionLocal
        from api.models import Player, Pick, PickResult
        import random

        db = SessionLocal()
        try:
            # Check if we already have comprehensive data
            player_count = db.query(Player).count()
            pick_count = db.query(Pick).count()

            if player_count >= 20 and pick_count >= 50:
                print(f"✅ Comprehensive data already exists ({player_count} players, {pick_count} picks)")
            else:
                # Clear any minimal test data
                db.query(PickResult).delete()
                db.query(Pick).delete()
                db.query(Player).delete()

                # Create realistic survivor pool participants
                participants = [
                    "Alice Johnson", "Bob Wilson", "Charlie Davis", "Diana Martinez",
                    "Eddie Thompson", "Fiona Chen", "George Rodriguez", "Hannah Kim",
                    "Ian O'Connor", "Julia Singh", "Kevin Brooks", "Lisa Garcia",
                    "Mike Anderson", "Nancy White", "Oscar Lopez", "Paula Jackson",
                    "Quinn Taylor", "Rachel Brown", "Steve Miller", "Tina Jones",
                    "Ursula Davis", "Victor Chang", "Wendy Smith", "Xavier Rivera",
                    "Yvonne Lee", "Zack Williams"
                ]

                # Create players
                print(f"   Creating {len(participants)} participants...")
                player_objects = []
                for name in participants:
                    player = Player(display_name=name)
                    db.add(player)
                    player_objects.append(player)

                db.flush()  # Get IDs

                # Create picks for weeks 1-3 with realistic eliminations
                strong_teams = ["KC", "BUF", "SF", "DAL", "MIA", "PHI", "CIN", "BAL", "DET", "JAX"]
                medium_teams = ["GB", "LAC", "MIN", "SEA", "HOU", "PIT", "IND", "TEN", "LV", "ATL"]
                eliminated_players = set()

                # Week 1 picks (completed)
                print("   Creating Week 1 picks and results...")
                for player in player_objects:
                    team = random.choice(strong_teams[:6])  # Safe picks
                    pick = Pick(player_id=player.player_id, season=2025, week=1, team_abbr=team)
                    db.add(pick)

                db.flush()

                # Week 1 results (15% elimination rate)
                week1_picks = db.query(Pick).filter(Pick.week == 1).all()
                for pick in week1_picks:
                    survived = random.random() > 0.15
                    if not survived:
                        eliminated_players.add(pick.player_id)
                    result = PickResult(pick_id=pick.pick_id, survived=survived, is_valid=True, is_locked=True)
                    db.add(result)

                # Week 2 picks (completed)
                print("   Creating Week 2 picks and results...")
                remaining_players = [p for p in player_objects if p.player_id not in eliminated_players]
                for player in remaining_players:
                    team = random.choice(strong_teams + medium_teams[:5])
                    pick = Pick(player_id=player.player_id, season=2025, week=2, team_abbr=team)
                    db.add(pick)

                db.flush()

                # Week 2 results (20% elimination rate)
                week2_picks = db.query(Pick).filter(Pick.week == 2).all()
                for pick in week2_picks:
                    survived = random.random() > 0.20
                    if not survived:
                        eliminated_players.add(pick.player_id)
                    result = PickResult(pick_id=pick.pick_id, survived=survived, is_valid=True, is_locked=True)
                    db.add(result)

                # Week 3 picks (current, no results yet)
                print("   Creating Week 3 picks (current week)...")
                final_remaining = [p for p in player_objects if p.player_id not in eliminated_players]
                for player in final_remaining:
                    team = random.choice(strong_teams + medium_teams)
                    pick = Pick(player_id=player.player_id, season=2025, week=3, team_abbr=team)
                    db.add(pick)

                db.commit()

                total_players = len(player_objects)
                remaining_count = len(final_remaining)
                print(f"✅ Created comprehensive mock data:")
                print(f"   Total Players: {total_players}")
                print(f"   Still Alive: {remaining_count}")
                print(f"   Survival Rate: {remaining_count/total_players*100:.1f}%")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Mock data creation failed: {e}")
        # Continue anyway

    print("\n🎉 NFL-only data population complete!")
    print("🌐 Your dashboard should now show NFL games!")
    print("📧 Share your Google Sheet with: survivorpool-sheets@nflsurvivorpool.iam.gserviceaccount.com")

    return True

if __name__ == "__main__":
    main()