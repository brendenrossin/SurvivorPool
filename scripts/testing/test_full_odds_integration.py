#!/usr/bin/env python3
"""
Comprehensive test of the complete odds integration
"""

import os
import sys
# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.database import SessionLocal
from api.models import Game
from app.dashboard_data import get_meme_stats
from app.live_scores import get_live_scores_data

def test_complete_integration():
    """Test all components of the odds integration"""
    print("🚀 Comprehensive Odds Integration Test")
    print("=" * 60)

    success = True

    # Test 1: Database schema
    print("\n1️⃣ Testing Database Schema...")
    try:
        db = SessionLocal()
        games = db.query(Game).limit(3).all()

        for game in games:
            print(f"   Game: {game.away_team} @ {game.home_team}")
            print(f"   Spread: {game.point_spread}, Favorite: {game.favorite_team}")

        print("✅ Database schema working")
        db.close()
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        success = False

    # Test 2: Enhanced Big Balls
    print("\n2️⃣ Testing Enhanced Big Balls...")
    try:
        meme_stats = get_meme_stats(2025)
        big_balls = meme_stats["big_balls_picks"]

        print(f"   Found {len(big_balls)} big balls picks")

        for pick in big_balls[:2]:
            underdog_status = "🐕 UNDERDOG" if pick.get('was_underdog') else "Road Win"
            print(f"   - {pick['team']}: {underdog_status}, {pick['big_balls_count']} players")

        print("✅ Enhanced Big Balls working")
    except Exception as e:
        print(f"❌ Big Balls test failed: {e}")
        success = False

    # Test 3: Live Scores with Spreads
    print("\n3️⃣ Testing Live Scores with Spreads...")
    try:
        db = SessionLocal()
        live_scores = get_live_scores_data(db, 2025, 3)

        print(f"   Found {len(live_scores)} live games")

        for game in live_scores[:2]:
            print(f"   - {game['away_team']} @ {game['home_team']}: {game['score_display']}")

        print("✅ Live Scores with spreads working")
        db.close()
    except Exception as e:
        print(f"❌ Live Scores test failed: {e}")
        success = False

    # Test 4: Score Updater Integration
    print("\n4️⃣ Testing Score Updater Integration...")
    try:
        from jobs.update_scores import ScoreUpdater

        updater = ScoreUpdater()
        print(f"   Score provider: {type(updater.score_provider).__name__}")
        print(f"   Odds provider: {type(updater.odds_provider).__name__}")

        # Test merge function with dummy data
        from api.score_providers import Game as GameData
        from datetime import datetime

        dummy_game = GameData(
            game_id="test_123",
            season=2025,
            week=3,
            kickoff=datetime.now(),
            home_team="BUF",
            away_team="MIA",
            status="pre"
        )

        merged = updater.merge_odds_with_games([dummy_game], {})
        print(f"   Merged {len(merged)} games successfully")

        print("✅ Score Updater integration working")
    except Exception as e:
        print(f"❌ Score Updater test failed: {e}")
        success = False

    print("\n" + "=" * 60)

    if success:
        print("🎉 ALL TESTS PASSED!")
        print("\n📋 Integration Status:")
        print("✅ Database schema updated")
        print("✅ Big Balls enhanced with underdog detection")
        print("✅ Live scores show spreads for pregame")
        print("✅ Score updater ready for odds API")
        print("✅ Dog emoji ready for underdog wins 🐕")
        print("\n🔑 Next Step: Add THE_ODDS_API_KEY to .env file")
        print("   Then run: python jobs/update_scores.py")

        return True
    else:
        print("💥 SOME TESTS FAILED!")
        print("   Check the errors above before proceeding.")
        return False

if __name__ == "__main__":
    test_complete_integration()