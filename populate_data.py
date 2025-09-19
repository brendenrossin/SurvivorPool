#!/usr/bin/env python3
"""
One-shot script to populate database with initial data
Run this on Railway to get data into your dashboard
"""

import sys
import os

def main():
    print("🚀 Populating SurvivorPool Database...")
    print("=" * 50)

    # Step 1: Ingest Google Sheets data
    print("\n📊 Step 1: Ingesting Google Sheets data...")
    try:
        from jobs.ingest_sheet import main as ingest_main
        result = ingest_main()
        if result:
            print("✅ Google Sheets data ingested successfully!")
        else:
            print("⚠️ Google Sheets ingestion completed with warnings")
    except Exception as e:
        print(f"❌ Google Sheets ingestion failed: {e}")
        # Continue anyway

    # Step 2: Get NFL scores and games
    print("\n🏈 Step 2: Fetching NFL scores...")
    try:
        from jobs.update_scores import main as scores_main
        result = scores_main()
        if result:
            print("✅ NFL scores updated successfully!")
        else:
            print("⚠️ NFL scores update completed with warnings")
    except Exception as e:
        print(f"❌ NFL scores update failed: {e}")
        # Continue anyway

    # Step 3: Backfill historical data if needed
    print("\n📅 Step 3: Backfilling historical data...")
    try:
        from jobs.backfill_weeks import main as backfill_main
        result = backfill_main()
        if result:
            print("✅ Historical data backfilled successfully!")
        else:
            print("⚠️ Historical backfill completed with warnings")
    except Exception as e:
        print(f"❌ Historical backfill failed: {e}")
        # Continue anyway

    print("\n🎉 Data population complete!")
    print("🌐 Your dashboard should now show survivor pool data!")

    return True

if __name__ == "__main__":
    main()