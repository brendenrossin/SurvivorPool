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

    # Step 2: Create some test data for demonstration
    print("\n👥 Step 2: Creating test player data...")
    try:
        from api.database import SessionLocal
        from api.models import Player, Pick

        db = SessionLocal()
        try:
            # Check if we already have players
            if db.query(Player).count() == 0:
                # Create test players
                test_players = [
                    "Alice Johnson",
                    "Bob Smith",
                    "Charlie Brown",
                    "Diana Prince",
                    "Eddie Murphy"
                ]

                for name in test_players:
                    player = Player(display_name=name)
                    db.add(player)

                db.commit()
                print(f"✅ Created {len(test_players)} test players")
            else:
                print("✅ Players already exist, skipping creation")

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Test data creation failed: {e}")
        # Continue anyway

    print("\n🎉 NFL-only data population complete!")
    print("🌐 Your dashboard should now show NFL games!")
    print("📧 Share your Google Sheet with: survivorpool-sheets@nflsurvivorpool.iam.gserviceaccount.com")

    return True

if __name__ == "__main__":
    main()