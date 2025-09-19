#!/usr/bin/env python3
"""
Railway Cron Job: Score Update
Runs multiple times per week to update NFL scores
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.update_scores import ScoreUpdater

def main():
    """Main cron job function - exits after completion"""
    print(f"🕐 Starting score update cron job at {datetime.now()}")

    try:
        updater = ScoreUpdater()
        success = updater.run(fetch_odds=False)  # Don't fetch odds, daily job handles that

        if success is not False:  # None or True means success
            print("✅ Score update completed successfully")
            sys.exit(0)
        else:
            print("❌ Score update failed")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Score update cron job crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()