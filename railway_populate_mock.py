#!/usr/bin/env python3
"""
Railway-specific mock data population script
This works with Railway's environment variables and startup sequence
"""

import sys
import os

def main():
    print("🎭 Railway Mock Survivor Data Population")
    print("=" * 50)

    # Verify we're in Railway environment
    if not os.getenv('DATABASE_URL'):
        print("❌ No DATABASE_URL found - this script is for Railway only")
        return False

    print(f"📊 DATABASE_URL: {os.getenv('DATABASE_URL')[:30]}...")

    try:
        # Import after environment is confirmed
        from api.database import SessionLocal
        from api.models import Player, Pick, PickResult
        import random

        print("📊 Connecting to Railway database...")
        db = SessionLocal()

        try:
            # Check current state
            player_count = db.query(Player).count()
            pick_count = db.query(Pick).count()

            print(f"Current state: {player_count} players, {pick_count} picks")

            if player_count >= 20 and pick_count >= 50:
                print("✅ Sufficient mock data already exists")
                return True

            # Clear existing minimal data
            print("🧹 Clearing existing data...")
            try:
                db.query(PickResult).delete()
                db.query(Pick).delete()
                db.query(Player).delete()
                db.commit()
                print("   ✅ Cleared existing data")
            except Exception as e:
                print(f"   ⚠️ Clear failed (might be empty): {e}")
                db.rollback()

            # Create comprehensive survivor pool participants
            participants = [
                "Alice Johnson", "Bob Wilson", "Charlie Davis", "Diana Martinez",
                "Eddie Thompson", "Fiona Chen", "George Rodriguez", "Hannah Kim",
                "Ian O'Connor", "Julia Singh", "Kevin Brooks", "Lisa Garcia",
                "Mike Anderson", "Nancy White", "Oscar Lopez", "Paula Jackson",
                "Quinn Taylor", "Rachel Brown", "Steve Miller", "Tina Jones",
                "Ursula Davis", "Victor Chang", "Wendy Smith", "Xavier Rivera",
                "Yvonne Lee", "Zack Williams"
            ]

            print(f"👥 Creating {len(participants)} participants...")
            players = []
            for name in participants:
                player = Player(display_name=name)
                db.add(player)
                players.append(player)

            db.flush()  # Get player IDs
            print(f"   ✅ Created {len(players)} players")

            # NFL teams for picks
            strong_teams = ["KC", "BUF", "SF", "DAL", "MIA", "PHI", "CIN", "BAL", "DET", "JAX"]
            medium_teams = ["GB", "LAC", "MIN", "SEA", "HOU", "PIT", "IND", "TEN", "LV", "ATL"]
            all_teams = strong_teams + medium_teams

            eliminated_players = set()

            # WEEK 1: Completed with results
            print("🏈 Creating Week 1 picks and results...")
            week1_picks = []
            for player in players:
                team = random.choice(strong_teams[:6])  # Safe early picks
                pick = Pick(
                    player_id=player.player_id,
                    season=2025,
                    week=1,
                    team_abbr=team
                )
                db.add(pick)
                week1_picks.append(pick)

            db.flush()  # Get pick IDs

            # Week 1 eliminations (15% realistic rate)
            for pick in week1_picks:
                survived = random.random() > 0.15
                if not survived:
                    eliminated_players.add(pick.player_id)

                result = PickResult(
                    pick_id=pick.pick_id,
                    survived=survived,
                    is_valid=True,
                    is_locked=True
                )
                db.add(result)

            print(f"   ✅ Week 1: {len(week1_picks)} picks, {len(eliminated_players)} eliminations")

            # WEEK 2: Completed with results
            print("🏈 Creating Week 2 picks and results...")
            week2_players = [p for p in players if p.player_id not in eliminated_players]
            week2_picks = []

            for player in week2_players:
                team = random.choice(strong_teams + medium_teams[:5])
                pick = Pick(
                    player_id=player.player_id,
                    season=2025,
                    week=2,
                    team_abbr=team
                )
                db.add(pick)
                week2_picks.append(pick)

            db.flush()

            # Week 2 eliminations (20% realistic rate)
            week2_eliminations = 0
            for pick in week2_picks:
                survived = random.random() > 0.20
                if not survived:
                    eliminated_players.add(pick.player_id)
                    week2_eliminations += 1

                result = PickResult(
                    pick_id=pick.pick_id,
                    survived=survived,
                    is_valid=True,
                    is_locked=True
                )
                db.add(result)

            print(f"   ✅ Week 2: {len(week2_picks)} picks, {week2_eliminations} eliminations")

            # WEEK 3: Current week (no results yet)
            print("🏈 Creating Week 3 picks (current week)...")
            week3_players = [p for p in players if p.player_id not in eliminated_players]
            week3_picks = []

            for player in week3_players:
                team = random.choice(all_teams)  # Any team for current week
                pick = Pick(
                    player_id=player.player_id,
                    season=2025,
                    week=3,
                    team_abbr=team
                )
                db.add(pick)
                week3_picks.append(pick)

            print(f"   ✅ Week 3: {len(week3_picks)} picks (current week)")

            # Commit everything
            db.commit()

            # Final summary
            total_players = len(players)
            survivors = len(week3_players)
            eliminated_count = len(eliminated_players)
            survival_rate = (survivors / total_players * 100) if total_players > 0 else 0

            print(f"\n🎉 Mock data created successfully!")
            print(f"   📊 Total Players: {total_players}")
            print(f"   ✅ Survivors: {survivors}")
            print(f"   ❌ Eliminated: {eliminated_count}")
            print(f"   📈 Survival Rate: {survival_rate:.1f}%")
            print(f"   📋 Total Picks: {len(week1_picks) + len(week2_picks) + len(week3_picks)}")

            return True

        except Exception as e:
            print(f"❌ Database operation failed: {e}")
            db.rollback()
            import traceback
            traceback.print_exc()
            return False
        finally:
            db.close()

    except Exception as e:
        print(f"❌ Mock data setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()

    if success:
        print("\n🎉 Railway mock data population complete!")
        print("🚀 Dashboard should now show full survivor pool data!")
    else:
        print("\n❌ Railway mock data population failed!")
        sys.exit(1)