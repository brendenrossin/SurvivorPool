#!/usr/bin/env python3
"""
Test NFL data ingestion only (skip Google Sheets)
"""

import os
import sys
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_nfl_data():
    """Test NFL API and populate local database"""
    print("🏈 Testing NFL Data Ingestion with REAL Environment")
    print("=" * 50)

    # Load the real .env file
    load_dotenv()

    # Override database to use local SQLite for testing
    os.environ['DATABASE_URL'] = 'sqlite:///debug_output/nfl_test.db'

    # Create debug directory
    os.makedirs("debug_output", exist_ok=True)

    try:
        # Import after env is set
        from api.database import engine, SessionLocal
        from api.models import Base, Game, Player, Pick, PickResult
        from api.score_providers import get_score_provider

        print("📊 Setting up local database...")
        Base.metadata.create_all(bind=engine)

        print("🌐 Fetching NFL games...")
        provider = get_score_provider("espn")
        current_week = provider.get_current_week(2025)
        games = provider.get_schedule_and_scores(2025, current_week)

        print(f"   ✅ Found {len(games)} games for Week {current_week}")

        # Insert games into database
        db = SessionLocal()
        try:
            games_added = 0
            for game in games:
                # Check if game exists
                existing = db.query(Game).filter(
                    Game.season == game.season,
                    Game.week == game.week,
                    Game.home_team == game.home_team,
                    Game.away_team == game.away_team
                ).first()

                if not existing:
                    db_game = Game(
                        season=game.season,
                        week=game.week,
                        game_id=game.game_id,
                        home_team=game.home_team,
                        away_team=game.away_team,
                        home_score=game.home_score,
                        away_score=game.away_score,
                        status=game.status,
                        kickoff=game.kickoff
                    )
                    db.add(db_game)
                    games_added += 1

            db.commit()
            print(f"   ✅ Added {games_added} new games to database")

            # Create a test player and pick
            test_player = Player(
                display_name="Test Player"
            )
            db.add(test_player)
            db.flush()  # Get the auto-generated ID

            # Add test pick for first game
            if games:
                first_game = games[0]
                test_pick = Pick(
                    player_id=test_player.player_id,
                    season=2025,
                    week=current_week,
                    team_abbr=first_game.home_team
                )
                db.add(test_pick)
                print(f"   ✅ Added test pick: {first_game.home_team}")

            db.commit()

            # Check final counts
            game_count = db.query(Game).count()
            player_count = db.query(Player).count()
            pick_count = db.query(Pick).count()

            print(f"\n📊 Database Summary:")
            print(f"   Games: {game_count}")
            print(f"   Players: {player_count}")
            print(f"   Picks: {pick_count}")

            # Export for inspection
            print(f"\n📁 Exporting data...")
            import json

            # Export games
            games_data = []
            for game in db.query(Game).all():
                games_data.append({
                    'game_id': game.game_id,
                    'season': game.season,
                    'week': game.week,
                    'home_team': game.home_team,
                    'away_team': game.away_team,
                    'home_score': game.home_score,
                    'away_score': game.away_score,
                    'status': game.status,
                    'kickoff': str(game.kickoff) if game.kickoff else None
                })

            with open('debug_output/nfl_games_test.json', 'w') as f:
                json.dump(games_data, f, indent=2)

            print(f"   ✅ NFL games saved to debug_output/nfl_games_test.json")
            print(f"   ✅ Database saved to debug_output/nfl_test.db")

            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ NFL test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_nfl_data()

    if success:
        print("\n🎉 NFL Data Test: SUCCESS!")
        print("📝 Check debug_output/nfl_games_test.json to see the data")
        print("💾 Check debug_output/nfl_test.db for the SQLite database")
    else:
        print("\n❌ NFL Data Test: FAILED!")