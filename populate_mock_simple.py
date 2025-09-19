#!/usr/bin/env python3
"""
Simple mock data population for Railway - just survivors, no NFL dependency
"""

import sys
import os

def main():
    print("🎭 Simple Mock Survivor Data Population")
    print("=" * 50)

    try:
        from api.database import SessionLocal
        from api.models import Player, Pick, PickResult
        import random

        print("📊 Connecting to database...")
        db = SessionLocal()

        try:
            # Check if we already have data
            player_count = db.query(Player).count()
            pick_count = db.query(Pick).count()

            print(f"Current data: {player_count} players, {pick_count} picks")

            if player_count >= 20:
                print("✅ Sufficient mock data already exists")
                return True

            # Clear existing data
            print("🧹 Clearing existing test data...")
            db.query(PickResult).delete()
            db.query(Pick).delete()
            db.query(Player).delete()
            db.commit()

            # Create participants
            participants = [
                "Alice Johnson", "Bob Wilson", "Charlie Davis", "Diana Martinez",
                "Eddie Thompson", "Fiona Chen", "George Rodriguez", "Hannah Kim",
                "Ian O'Connor", "Julia Singh", "Kevin Brooks", "Lisa Garcia",
                "Mike Anderson", "Nancy White", "Oscar Lopez", "Paula Jackson",
                "Quinn Taylor", "Rachel Brown", "Steve Miller", "Tina Jones",
                "Ursula Davis", "Victor Chang", "Wendy Smith", "Xavier Rivera"
            ]

            print(f"👥 Creating {len(participants)} participants...")
            players = []
            for name in participants:
                player = Player(display_name=name)
                db.add(player)
                players.append(player)

            db.flush()  # Get player IDs

            # Common NFL teams
            teams = ["KC", "BUF", "SF", "DAL", "MIA", "PHI", "CIN", "BAL", "DET", "JAX",
                    "GB", "LAC", "MIN", "SEA", "HOU", "PIT", "IND", "TEN"]

            eliminated = set()

            # Week 1 picks and results
            print("🏈 Creating Week 1 data...")
            for player in players:
                team = random.choice(teams[:8])  # Safe picks
                pick = Pick(player_id=player.player_id, season=2025, week=1, team_abbr=team)
                db.add(pick)

            db.flush()

            # Week 1 eliminations (15%)
            week1_picks = db.query(Pick).filter(Pick.week == 1).all()
            for pick in week1_picks:
                survived = random.random() > 0.15
                if not survived:
                    eliminated.add(pick.player_id)

                result = PickResult(
                    pick_id=pick.pick_id,
                    survived=survived,
                    is_valid=True,
                    is_locked=True
                )
                db.add(result)

            # Week 2 picks and results
            print("🏈 Creating Week 2 data...")
            alive_players = [p for p in players if p.player_id not in eliminated]
            for player in alive_players:
                team = random.choice(teams)
                pick = Pick(player_id=player.player_id, season=2025, week=2, team_abbr=team)
                db.add(pick)

            db.flush()

            # Week 2 eliminations (20%)
            week2_picks = db.query(Pick).filter(Pick.week == 2).all()
            for pick in week2_picks:
                survived = random.random() > 0.20
                if not survived:
                    eliminated.add(pick.player_id)

                result = PickResult(
                    pick_id=pick.pick_id,
                    survived=survived,
                    is_valid=True,
                    is_locked=True
                )
                db.add(result)

            # Week 3 picks (current week, no results)
            print("🏈 Creating Week 3 data...")
            final_alive = [p for p in players if p.player_id not in eliminated]
            for player in final_alive:
                team = random.choice(teams)
                pick = Pick(player_id=player.player_id, season=2025, week=3, team_abbr=team)
                db.add(pick)

            db.commit()

            # Summary
            total = len(players)
            remaining = len(final_alive)
            eliminated_count = len(eliminated)

            print(f"\n✅ Mock data created successfully!")
            print(f"   Total players: {total}")
            print(f"   Still alive: {remaining}")
            print(f"   Eliminated: {eliminated_count}")
            print(f"   Survival rate: {remaining/total*100:.1f}%")

            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Mock data creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()

    if success:
        print("\n🎉 Simple mock data creation complete!")
    else:
        print("\n❌ Mock data creation failed!")