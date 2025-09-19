#!/usr/bin/env python3
"""
Test the odds integration WITHOUT requiring an API key
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.database import SessionLocal
from api.models import Game
from jobs.update_scores import ScoreUpdater

def test_odds_without_api_key():
    """Test that the odds integration doesn't break without an API key"""
    print("🧪 Testing odds integration without API key...")

    # Make sure no API key is set
    if "THE_ODDS_API_KEY" in os.environ:
        del os.environ["THE_ODDS_API_KEY"]

    try:
        # This should work without breaking
        updater = ScoreUpdater()
        print("✅ ScoreUpdater created successfully")

        # Test the odds provider
        odds_data = updater.odds_provider.get_nfl_odds(2025, 3)
        print(f"✅ Odds provider returned: {len(odds_data)} games (expected 0 without API key)")

        # Test merging with empty odds
        from api.score_providers import Game as GameData
        from datetime import datetime

        fake_game = GameData(
            game_id="test_123",
            season=2025,
            week=3,
            kickoff=datetime.now(),
            home_team="BUF",
            away_team="MIA",
            status="pre"
        )

        merged_games = updater.merge_odds_with_games([fake_game], odds_data)
        print(f"✅ Merged {len(merged_games)} games without odds data")

        print("✅ All tests passed - odds integration is safe without API key!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

    return True

def test_database_schema():
    """Test that the new database columns exist"""
    print("\n🗄️ Testing database schema...")

    db = SessionLocal()
    try:
        # Test that we can query the new columns
        games = db.query(Game.game_id, Game.point_spread, Game.favorite_team).limit(1).all()
        print("✅ Database schema updated successfully")

        # Check if any games have odds data
        games_with_odds = db.query(Game).filter(
            Game.point_spread.isnot(None)
        ).count()
        print(f"✅ Games with odds data: {games_with_odds}")

    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        return False
    finally:
        db.close()

    return True

if __name__ == "__main__":
    print("🚀 Testing Odds Integration")
    print("=" * 50)

    success = True
    success &= test_odds_without_api_key()
    success &= test_database_schema()

    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Ready to add API key and test with real data.")
    else:
        print("💥 Some tests failed. Check the errors above.")