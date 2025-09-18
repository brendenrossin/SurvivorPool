#!/usr/bin/env python3
"""
Railway Cron Job: Update NFL scores and game results
Runs every 15 minutes during game days to keep scores fresh
"""

import os
import sys
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Run score updates as a cron job"""
    print(f"🕐 Cron Job Started: Score Updates at {datetime.now()} UTC")

    try:
        load_dotenv()

        # Import and run the score updater
        from jobs.update_scores import ScoreUpdater

        updater = ScoreUpdater()
        result = updater.run()

        if result:
            print("✅ Score updates completed successfully")
        else:
            print("⚠️  Score updates completed with warnings")

    except Exception as e:
        print(f"❌ Score updates failed: {e}")
        traceback.print_exc()
        # Exit with error code for Railway monitoring
        sys.exit(1)

    print("🏁 Cron Job Completed: Score Updates")
    # Successful exit
    sys.exit(0)

if __name__ == "__main__":
    main()