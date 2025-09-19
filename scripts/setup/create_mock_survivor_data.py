#!/usr/bin/env python3
"""
Create comprehensive mock survivor pool data for dashboard testing
This will be automatically replaced when real Google Sheets data comes in
"""

import os
import sys
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_comprehensive_mock_data():
    """Create realistic survivor pool mock data across multiple weeks"""
    print("🎭 Creating Comprehensive Mock Survivor Pool Data")
    print("=" * 60)

    # Load environment
    load_dotenv()
    os.environ['DATABASE_URL'] = 'sqlite:///debug_output/mock_survivor.db'

    try:
        from api.database import engine, SessionLocal
        from api.models import Base, Player, Pick, Game, PickResult

        print("📊 Setting up database...")
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            # Clear existing test data
            db.query(PickResult).delete()
            db.query(Pick).delete()
            db.query(Player).delete()
            db.commit()

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
            print(f"👥 Creating {len(participants)} participants...")
            player_objects = []
            for name in participants:
                player = Player(display_name=name)
                db.add(player)
                player_objects.append(player)

            db.flush()  # Get IDs

            # Define teams commonly picked in survivor pools (strong teams)
            strong_teams = ["KC", "BUF", "SF", "DAL", "MIA", "PHI", "CIN", "BAL", "DET", "JAX"]
            medium_teams = ["GB", "LAC", "MIN", "SEA", "HOU", "PIT", "IND", "TEN", "LV", "ATL"]
            weak_teams = ["NYJ", "NE", "CLE", "DEN", "WAS", "NYG", "CHI", "TB", "CAR", "AZ"]

            all_teams = strong_teams + medium_teams + weak_teams

            # Create picks for weeks 1-2 (completed) and week 3 (current)
            eliminated_players = set()

            print("🏈 Creating Week 1 picks (completed)...")
            week1_results = create_week_picks(db, player_objects, 1, strong_teams, eliminated_players)

            print("🏈 Creating Week 2 picks (completed)...")
            week2_results = create_week_picks(db, player_objects, 2, strong_teams + medium_teams, eliminated_players)

            print("🏈 Creating Week 3 picks (current)...")
            remaining_players = [p for p in player_objects if p.player_id not in eliminated_players]
            week3_results = create_week_picks(db, remaining_players, 3, all_teams, eliminated_players, current_week=True)

            db.commit()

            # Print summary
            total_players = len(player_objects)
            remaining_count = len(remaining_players)
            eliminated_count = len(eliminated_players)

            print(f"\n📊 Mock Data Summary:")
            print(f"   Total Players: {total_players}")
            print(f"   Still Alive: {remaining_count}")
            print(f"   Eliminated: {eliminated_count}")
            print(f"   Survival Rate: {remaining_count/total_players*100:.1f}%")

            # Export for inspection
            print(f"\n📁 Exporting mock data...")
            export_mock_data(db)

            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Mock data creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_week_picks(db, players, week, available_teams, eliminated_players, current_week=False):
    """Create picks for a specific week with realistic survivor behavior"""
    from api.models import Pick, PickResult

    # Create picks for remaining players
    picks_created = 0
    for player in players:
        if player.player_id in eliminated_players:
            continue

        # Players tend to pick different teams (strategy)
        # Earlier weeks = safer picks, later weeks = more desperate picks
        if week == 1:
            team = random.choice(available_teams[:6])  # Very safe picks
        elif week == 2:
            team = random.choice(available_teams[:10])  # Still pretty safe
        else:
            team = random.choice(available_teams)  # Any team

        pick = Pick(
            player_id=player.player_id,
            season=2025,
            week=week,
            team_abbr=team
        )
        db.add(pick)
        picks_created += 1

    db.flush()  # Get pick IDs

    # Create results for completed weeks (1 and 2)
    if not current_week:
        picks = db.query(Pick).filter(Pick.week == week).all()
        results_created = 0

        for pick in picks:
            # Simulate some eliminations (10-20% per week is realistic)
            elimination_chance = 0.15 if week == 1 else 0.20  # Week 2 slightly harder

            survived = random.random() > elimination_chance
            if not survived:
                eliminated_players.add(pick.player_id)

            result = PickResult(
                pick_id=pick.pick_id,
                survived=survived,
                is_valid=True,
                is_locked=True  # Past weeks are locked
            )
            db.add(result)
            results_created += 1

        print(f"   Week {week}: {picks_created} picks, {results_created} results, {len([p for p in picks if p.player_id in eliminated_players])} eliminations")
    else:
        print(f"   Week {week}: {picks_created} picks (current week, no results yet)")

    return picks_created

def export_mock_data(db):
    """Export mock data for inspection"""
    from api.models import Player, Pick, PickResult
    import json

    os.makedirs("debug_output", exist_ok=True)

    # Export players
    players = db.query(Player).all()
    players_data = [{"id": p.player_id, "name": p.display_name} for p in players]

    # Export picks with results
    picks_data = []
    picks = db.query(Pick, PickResult).outerjoin(PickResult).all()

    for pick, result in picks:
        pick_data = {
            "player_id": pick.player_id,
            "week": pick.week,
            "team": pick.team_abbr,
            "survived": result.survived if result else None,
            "locked": result.is_locked if result else False
        }
        picks_data.append(pick_data)

    # Save files
    with open('debug_output/mock_players.json', 'w') as f:
        json.dump(players_data, f, indent=2)

    with open('debug_output/mock_picks.json', 'w') as f:
        json.dump(picks_data, f, indent=2)

    print(f"   ✅ Players saved: {len(players_data)} players")
    print(f"   ✅ Picks saved: {len(picks_data)} picks")
    print(f"   ✅ Database: debug_output/mock_survivor.db")

if __name__ == "__main__":
    success = create_comprehensive_mock_data()

    if success:
        print("\n🎉 Comprehensive Mock Data Created!")
        print("📝 Check debug_output/ to see all the data")
        print("🚀 Now deploy to Railway to populate your dashboard!")
    else:
        print("\n❌ Mock Data Creation Failed!")