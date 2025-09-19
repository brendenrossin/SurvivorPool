#!/usr/bin/env python3
"""
Test Google Sheets ingestion only with real environment
"""

import os
import sys
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sheets_data():
    """Test Google Sheets API and populate local database"""
    print("📊 Testing Google Sheets Data Ingestion with REAL Environment")
    print("=" * 50)

    # Load the real .env file
    load_dotenv()

    # Override database to use local SQLite for testing
    os.environ['DATABASE_URL'] = 'sqlite:///debug_output/sheets_test.db'

    # Create debug directory
    os.makedirs("debug_output", exist_ok=True)

    try:
        # Import after env is set
        from api.database import engine, SessionLocal
        from api.models import Base, Player, Pick
        from jobs.ingest_sheet import SheetIngestor

        print("📊 Setting up local database...")
        Base.metadata.create_all(bind=engine)

        print("📈 Testing Google Sheets ingestion...")
        ingestor = SheetIngestor()
        result = ingestor.run()

        # Check what we got
        db = SessionLocal()
        try:
            player_count = db.query(Player).count()
            pick_count = db.query(Pick).count()

            print(f"\n📊 Database Summary:")
            print(f"   Players: {player_count}")
            print(f"   Picks: {pick_count}")

            if player_count > 0:
                # Export for inspection
                print(f"\n📁 Exporting data...")
                import json

                # Export players
                players_data = []
                for player in db.query(Player).all():
                    players_data.append({
                        'player_id': player.player_id,
                        'display_name': player.display_name
                    })

                # Export picks
                picks_data = []
                for pick in db.query(Pick).all():
                    picks_data.append({
                        'pick_id': pick.pick_id,
                        'player_id': pick.player_id,
                        'season': pick.season,
                        'week': pick.week,
                        'team_abbr': pick.team_abbr,
                        'source': pick.source,
                        'picked_at': str(pick.picked_at)
                    })

                with open('debug_output/sheets_players_test.json', 'w') as f:
                    json.dump(players_data, f, indent=2)

                with open('debug_output/sheets_picks_test.json', 'w') as f:
                    json.dump(picks_data, f, indent=2)

                print(f"   ✅ Players saved to debug_output/sheets_players_test.json")
                print(f"   ✅ Picks saved to debug_output/sheets_picks_test.json")
                print(f"   ✅ Database saved to debug_output/sheets_test.db")

            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Sheets test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sheets_data()

    if success:
        print("\n🎉 Google Sheets Data Test: SUCCESS!")
        print("📝 Check debug_output/ files to see the data")
    else:
        print("\n❌ Google Sheets Data Test: FAILED!")