#!/usr/bin/env python3
"""
Railway Cron Job: Daily Odds Update
Runs daily at 8:00 AM EST to fetch betting odds
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.update_odds import OddsUpdater

def main():
    """Main cron job function - exits after completion"""
    print(f"🕐 Starting daily odds cron job at {datetime.now()}")

    try:
        updater = OddsUpdater()
        success = updater.run()

        if success is not False:  # None or True means success
            print("✅ Daily odds update completed successfully")
            sys.exit(0)
        else:
            print("❌ Daily odds update failed")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Daily odds cron job crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()