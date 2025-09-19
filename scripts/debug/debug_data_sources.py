#!/usr/bin/env python3
"""
Debug script to test all data sources and save outputs for inspection
"""

import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def test_google_sheets():
    """Test Google Sheets API and save output"""
    print("🧪 Testing Google Sheets API...")

    try:
        from api.sheets import GoogleSheetsClient

        client = GoogleSheetsClient()

        # Test raw data fetch
        print("   Fetching raw sheet data...")
        raw_data = client.get_picks_data()

        # Save raw data
        with open("debug_output/google_sheets_raw.json", "w") as f:
            json.dump(raw_data, f, indent=2)

        print(f"   ✅ Raw data saved: {len(raw_data)} rows")

        # Test parsed data
        print("   Parsing sheet data...")
        parsed_data = client.parse_picks_data(raw_data)

        # Save parsed data
        with open("debug_output/google_sheets_parsed.json", "w") as f:
            json.dump(parsed_data, f, indent=2)

        print(f"   ✅ Parsed data saved: {len(parsed_data['players'])} players, {len(parsed_data['picks'])} picks")

        # Pretty print summary
        print("\n📊 GOOGLE SHEETS SUMMARY:")
        print(f"   Players: {len(parsed_data['players'])}")
        print(f"   Total picks: {len(parsed_data['picks'])}")

        # Show sample picks by week
        weeks = {}
        for pick in parsed_data['picks']:
            week = pick['week']
            if week not in weeks:
                weeks[week] = []
            weeks[week].append(pick)

        for week in sorted(weeks.keys()):
            print(f"   Week {week}: {len(weeks[week])} picks")

        return True

    except Exception as e:
        print(f"   ❌ Google Sheets failed: {e}")

        # Save error details
        with open("debug_output/google_sheets_error.txt", "w") as f:
            f.write(f"Error: {e}\n")
            f.write(f"Time: {datetime.now()}\n")

        return False

def test_nfl_api():
    """Test NFL API and save output"""
    print("\n🧪 Testing NFL API...")

    try:
        from api.score_providers import get_score_provider

        provider = get_score_provider("espn")
        season = int(os.getenv("NFL_SEASON", 2025))

        # Test current week detection
        print("   Getting current week...")
        current_week = provider.get_current_week(season)
        print(f"   ✅ Current week: {current_week}")

        # Test schedule and scores for current week
        print(f"   Fetching games for Week {current_week}...")
        games = provider.get_schedule_and_scores(season, current_week)

        # Convert games to JSON-serializable format
        games_data = []
        for game in games:
            games_data.append({
                "game_id": game.game_id,
                "season": game.season,
                "week": game.week,
                "kickoff": game.kickoff.isoformat(),
                "home_team": game.home_team,
                "away_team": game.away_team,
                "status": game.status,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "winner_abbr": game.winner_abbr
            })

        # Save games data
        with open("debug_output/nfl_games.json", "w") as f:
            json.dump({
                "season": season,
                "current_week": current_week,
                "games": games_data
            }, f, indent=2)

        print(f"   ✅ Games data saved: {len(games)} games")

        # Pretty print summary
        print(f"\n🏈 NFL API SUMMARY:")
        print(f"   Season: {season}")
        print(f"   Current Week: {current_week}")
        print(f"   Games this week: {len(games)}")

        # Show game status breakdown
        status_counts = {}
        for game in games:
            status = game.status
            status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            print(f"   {status}: {count} games")

        return True

    except Exception as e:
        print(f"   ❌ NFL API failed: {e}")

        # Save error details
        with open("debug_output/nfl_api_error.txt", "w") as f:
            f.write(f"Error: {e}\n")
            f.write(f"Time: {datetime.now()}\n")

        return False

def test_database_connection():
    """Test database connection and show current data"""
    print("\n🧪 Testing Database Connection...")

    try:
        from api.database import SessionLocal
        from api.models import Player, Pick, Game, PickResult

        db = SessionLocal()

        # Test basic connection
        players_count = db.query(Player).count()
        picks_count = db.query(Pick).count()
        games_count = db.query(Game).count()
        results_count = db.query(PickResult).count()

        print(f"   ✅ Database connected successfully")

        # Save database summary
        db_summary = {
            "timestamp": datetime.now().isoformat(),
            "players": players_count,
            "picks": picks_count,
            "games": games_count,
            "pick_results": results_count
        }

        with open("debug_output/database_summary.json", "w") as f:
            json.dump(db_summary, f, indent=2)

        print(f"\n💾 DATABASE SUMMARY:")
        print(f"   Players: {players_count}")
        print(f"   Picks: {picks_count}")
        print(f"   Games: {games_count}")
        print(f"   Pick Results: {results_count}")

        # If we have data, show some samples
        if players_count > 0:
            print(f"\n   Sample Players:")
            sample_players = db.query(Player).limit(5).all()
            for player in sample_players:
                print(f"     - {player.display_name}")

        if games_count > 0:
            print(f"\n   Sample Games:")
            sample_games = db.query(Game).limit(3).all()
            for game in sample_games:
                print(f"     - Week {game.week}: {game.away_team} @ {game.home_team} ({game.status})")

        db.close()
        return True

    except Exception as e:
        print(f"   ❌ Database failed: {e}")

        # Save error details
        with open("debug_output/database_error.txt", "w") as f:
            f.write(f"Error: {e}\n")
            f.write(f"Time: {datetime.now()}\n")

        return False

def main():
    """Run all tests"""
    print("🚀 SurvivorPool Data Source Debug Tool")
    print("=" * 50)

    # Create debug output directory
    os.makedirs("debug_output", exist_ok=True)

    # Test all data sources
    results = []

    results.append(("Google Sheets", test_google_sheets()))
    results.append(("NFL API", test_nfl_api()))
    results.append(("Database", test_database_connection()))

    # Summary
    print("\n" + "=" * 50)
    print("🎯 SUMMARY:")

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False

    print(f"\n📁 Debug files saved to: debug_output/")
    print("   You can open these in VS Code to inspect the data!")

    if all_passed:
        print("\n🎉 All tests passed! Your data sources are working!")
    else:
        print("\n⚠️  Some tests failed. Check the error files in debug_output/")

if __name__ == "__main__":
    main()